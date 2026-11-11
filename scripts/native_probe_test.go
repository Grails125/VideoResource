package core

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/netip"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	tlsclient "github.com/bogdanfinn/tls-client"
	"github.com/bogdanfinn/tls-client/profiles"
)

type repositoryHealthOutcome struct {
	Status  string `json:"status"`
	Message string `json:"message"`
	MS      *int64 `json:"ms,omitempty"`
}

type repositoryHealthInput struct {
	Version int             `json:"version"`
	Key     string          `json:"key"`
	Site    json.RawMessage `json:"site"`
}

var repositoryHealthImage = errors.New("source image body blocked")

type repositoryHealthTransport struct {
	base     http.RoundTripper
	requests atomic.Int64
}

func (transport *repositoryHealthTransport) RoundTrip(request *http.Request) (*http.Response, error) {
	if request.URL == nil || request.URL.User != nil || request.URL.Hostname() == "" || request.URL.Scheme != "https" && request.URL.Scheme != "http" {
		return nil, errors.New("native health request URL invalid")
	}
	if transport.requests.Add(1) > 64 {
		return nil, errors.New("native health request budget exceeded")
	}
	if request.Method != http.MethodHead {
		path := strings.ToLower(request.URL.Path)
		for _, suffix := range []string{".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif", ".ico"} {
			if strings.HasSuffix(path, suffix) {
				return nil, repositoryHealthImage
			}
		}
	}
	response, err := transport.base.RoundTrip(request)
	if err == nil && request.Method != http.MethodHead && strings.HasPrefix(strings.ToLower(response.Header.Get("Content-Type")), "image/") {
		response.Body.Close()
		return nil, repositoryHealthImage
	}
	return response, err
}

func repositoryHealthPublicDial(ctx context.Context, network, address string) (net.Conn, error) {
	host, port, err := net.SplitHostPort(address)
	if err != nil {
		return nil, err
	}
	addresses, err := net.DefaultResolver.LookupIPAddr(ctx, host)
	if err != nil || len(addresses) == 0 {
		return nil, errors.New("native health DNS failed")
	}
	for _, address := range addresses {
		ip := address.IP
		if !repositoryHealthPublicIP(ip) {
			return nil, errors.New("native health refuses non-public address")
		}
	}
	dialer := net.Dialer{Timeout: 8 * time.Second}
	return dialer.DialContext(ctx, network, net.JoinHostPort(addresses[0].IP.String(), port))
}

func repositoryHealthPublicIP(ip net.IP) bool {
	address, ok := netip.AddrFromSlice(ip)
	if !ok {
		return false
	}
	address = address.Unmap()
	if !address.IsGlobalUnicast() || address.IsPrivate() || address.IsLoopback() || address.IsLinkLocalUnicast() || address.IsUnspecified() {
		return false
	}
	for _, value := range []string{"0.0.0.0/8", "100.64.0.0/10", "192.0.0.0/24", "192.0.2.0/24", "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24", "240.0.0.0/4", "2001::/23", "2001:db8::/32", "2002::/16", "3fff::/20"} {
		if netip.MustParsePrefix(value).Contains(address) {
			return false
		}
	}
	return true
}

func repositoryHealthStep(ctx context.Context, stage string, budget time.Duration, work func(context.Context) (string, error)) repositoryHealthOutcome {
	started := time.Now()
	stepContext, cancel := context.WithTimeout(ctx, budget)
	defer cancel()
	message, err := work(stepContext)
	ms := time.Since(started).Milliseconds()
	outcome := repositoryHealthOutcome{Status: "ok", Message: message, MS: &ms}
	if err != nil {
		outcome.Status, outcome.Message = "fail", "原生"+stage+"请求或解析失败"
		if stepContext.Err() != nil {
			outcome.Message = "原生" + stage + "超时"
		}
		if errors.Is(err, repositoryHealthImage) {
			outcome.Status, outcome.Message = "unknown", "图片正文请求已阻止"
		}
		if errors.Is(err, errHeitaoAgeConfirmation) {
			outcome.Status, outcome.Message = "unknown", "需要本人访问确认"
		}
		if errors.Is(err, errSoraniLoginRequired) || errors.Is(err, errSoraniLoginExpired) {
			outcome.Status, outcome.Message = "unknown", "需要来源账号授权"
		}
	}
	return outcome
}

func repositoryHealthBytes(ctx context.Context, d *Downloader, media providerMedia, address string, full bool) ([]byte, error) {
	request, err := http.NewRequestWithContext(providerMediaContext(ctx, media.credentials), http.MethodGet, address, nil)
	if err != nil || !isProviderHTTPMediaURL(address) {
		return nil, errors.New("invalid sample address")
	}
	request.Header.Set("Referer", media.Referer)
	if !full {
		request.Header.Set("Range", "bytes=0-1048575")
	}
	response, err := d.doMediaRequest(request)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	if response.StatusCode != 200 && response.StatusCode != 206 {
		return nil, errors.New("sample HTTP refused")
	}
	limit := int64(1 << 20)
	if full {
		limit++
	}
	body, err := io.ReadAll(io.LimitReader(response.Body, limit))
	if err != nil || len(body) == 0 || full && len(body) > 1<<20 {
		return nil, errors.New("invalid bounded sample")
	}
	return body, nil
}

func repositoryHealthSample(ctx context.Context, d *Downloader, media providerMedia) ([]byte, string, error) {
	if media.DASH != nil {
		return nil, "DASH 已解析，需客户端分轨验证", nil
	}
	if len(media.HLSKey) != 0 || len(media.CENCKey) != 0 {
		return nil, "加密媒体已解析，需客户端验证", nil
	}
	address, playlist := media.URL, media.Playlist
	for depth := 0; depth < 3; depth++ {
		body := []byte(playlist)
		if playlist == "" {
			var err error
			body, err = repositoryHealthBytes(ctx, d, media, address, false)
			if err != nil {
				return nil, "", err
			}
		}
		trimmed := bytes.TrimSpace(bytes.TrimPrefix(body, []byte{239, 187, 191}))
		if !bytes.HasPrefix(trimmed, []byte("#EXTM3U")) {
			if len(trimmed) == 0 || trimmed[0] == '<' || trimmed[0] == '{' {
				return nil, "网页或封包媒体需客户端验证", nil
			}
			return body, "", nil
		}
		if len(body) >= 1<<20 {
			return nil, "清单超过抽样上限", nil
		}
		lines := strings.Split(string(trimmed), "\n")
		base, err := url.Parse(address)
		if err != nil {
			return nil, "", err
		}
		resolve := func(raw string) string {
			ref, err := url.Parse(strings.TrimSpace(raw))
			if err != nil {
				return ""
			}
			return base.ResolveReference(ref).String()
		}
		initialization, master, segment := "", false, ""
		for _, raw := range lines {
			line := strings.TrimSpace(raw)
			if strings.HasPrefix(line, "#EXT-X-KEY:") && nativeHLSAttributes(line)["METHOD"] != "NONE" ||
				strings.HasPrefix(line, "#EXT-X-SESSION-KEY:") || strings.HasPrefix(line, "#EXT-X-BYTERANGE:") || strings.HasPrefix(line, "#EXT-X-PART:") {
				return nil, "加密或范围媒体已解析，需客户端验证", nil
			}
			if strings.HasPrefix(line, "#EXT-X-MAP:") {
				attributes := nativeHLSAttributes(line)
				if attributes["BYTERANGE"] != "" {
					return nil, "范围初始化需客户端验证", nil
				}
				initialization = resolve(attributes["URI"])
			}
			if strings.HasPrefix(line, "#EXT-X-STREAM-INF:") {
				master = true
			}
			if line != "" && !strings.HasPrefix(line, "#") {
				segment = resolve(line)
				break
			}
		}
		if !isProviderHTTPMediaURL(segment) {
			return nil, "", errors.New("playlist missing sample")
		}
		if master {
			address, playlist = segment, ""
			continue
		}
		var init []byte
		if initialization != "" {
			init, err = repositoryHealthBytes(ctx, d, media, initialization, true)
			if err != nil {
				return nil, "", err
			}
		}
		body, err = repositoryHealthBytes(ctx, d, media, segment, false)
		return append(init, body...), "", err
	}
	return nil, "HLS 层级超过抽样上限", nil
}

func repositoryHealthDecode(ctx context.Context, body []byte) error {
	executable := os.Getenv("YINGCHUAN_HEALTH_FFMPEG")
	if executable == "" {
		return errors.New("FFmpeg missing")
	}
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	command := exec.CommandContext(ctx, executable, "-nostdin", "-hide_banner", "-loglevel", "error", "-max_alloc", "67108864",
		"-protocol_whitelist", "pipe", "-format_whitelist", "mpegts,mpeg,mov,matroska,flv,avi", "-probesize", "2097152",
		"-analyzeduration", "2000000", "-threads", "1", "-i", "pipe:0", "-map", "0:v:0", "-frames:v", "1", "-threads", "1", "-f", "null", "-progress", "pipe:1", "-")
	command.Stdin = bytes.NewReader(body)
	output, err := command.Output()
	if err != nil || !regexp.MustCompile(`(?m)^frame=\s*[1-9][0-9]*\s*$`).Match(output) {
		return errors.New("sample did not decode first frame")
	}
	return nil
}

func repositoryHealthProbe(ctx context.Context, engine *nativeEngine, input repositoryHealthInput) map[string]repositoryHealthOutcome {
	result := map[string]repositoryHealthOutcome{}
	for _, field := range []string{"catalog", "cover", "search", "playback"} {
		result[field] = repositoryHealthOutcome{Status: "unknown", Message: "上游步骤不可用，未检测"}
	}
	var site struct {
		Adapter string `json:"adapter"`
	}
	if json.Unmarshal(input.Site, &site) != nil || input.Version != 1 || !nativeOptionalSource(site.Adapter) {
		result["catalog"] = repositoryHealthOutcome{Status: "fail", Message: "原生来源身份无效或属于内置源"}
		return result
	}
	config, _ := json.Marshal(map[string]any{"cache_time": 7200, "api_site": map[string]json.RawMessage{input.Key: input.Site}})
	registry := engine.downloader.generalMediaRegistry()
	registry.mu.RLock()
	revision := registry.revision
	registry.mu.RUnlock()
	payload, _ := json.Marshal(map[string]any{"text": string(config), "revision": revision})
	_, err := engine.generalMedia(ctx, nativeInput{Command: "apply", GeneralMedia: payload, GeneralMediaAccess: nativeGeneralMediaAccess{Admin: true, Unlocked: true}})
	if err != nil {
		result["catalog"] = repositoryHealthOutcome{Status: "fail", Message: "原生配置未通过客户端校验"}
		return result
	}
	var page nativeCatalogResult
	result["catalog"] = repositoryHealthStep(ctx, "目录", 18*time.Second, func(c context.Context) (string, error) {
		request := nativeInput{Action: "catalog", Source: site.Adapter, Page: 1, Force: true}
		if err := engine.authorizeConfiguredSource(request); err != nil {
			return "", err
		}
		var err error
		page, err = engine.nativeCatalog(c, request)
		if err == nil && len(page.Items) == 0 {
			err = errors.New("empty catalog")
		}
		return "客户端原生目录有效", err
	})
	if result["catalog"].Status != "ok" {
		return result
	}
	drama := page.Items[0]
	for _, candidate := range page.Items {
		if candidate.VIP == nil || !*candidate.VIP {
			drama = candidate
			break
		}
	}
	result["search"] = repositoryHealthStep(ctx, "搜索", 18*time.Second, func(c context.Context) (string, error) {
		page, err := engine.nativeCatalog(c, nativeInput{Source: site.Adapter, Page: 1, Query: drama.Title, Force: true})
		if err != nil {
			return "", err
		}
		for _, row := range page.Items {
			if row.ID == drama.ID {
				if page.LocalSearch {
					return "客户端有界本地搜索命中", nil
				}
				return "客户端原生搜索命中", nil
			}
		}
		return "", errors.New("search did not match sample identity")
	})
	result["cover"] = repositoryHealthStep(ctx, "封面", 8*time.Second, func(c context.Context) (string, error) {
		if drama.Cover == "" {
			return "未提供封面地址", nil
		}
		request, err := http.NewRequestWithContext(c, http.MethodHead, drama.Cover, nil)
		if err != nil {
			return "", err
		}
		request.Header.Set("Referer", nativeCoverReferer(engine.downloader, drama.Source, drama.Cover))
		response, err := engine.downloader.client.Do(request)
		if err != nil {
			return "", err
		}
		defer response.Body.Close()
		if response.StatusCode == 405 || response.StatusCode == 501 {
			return "封面不支持 HEAD", nil
		}
		if response.StatusCode == 200 && !strings.HasPrefix(strings.ToLower(response.Header.Get("Content-Type")), "image/") {
			return "封面响应头未证明图片类型", nil
		}
		if response.StatusCode != 200 || response.Header.Get("Content-Length") == "0" {
			return "", errors.New("cover headers invalid")
		}
		return "仅 HEAD 可达", nil
	})
	if result["cover"].Message == "未提供封面地址" || result["cover"].Message == "封面不支持 HEAD" || result["cover"].Message == "封面响应头未证明图片类型" {
		outcome := result["cover"]
		outcome.Status = "unknown"
		result["cover"] = outcome
	}
	var chapters []Chapter
	unknown := ""
	result["playback"] = repositoryHealthStep(ctx, "播放", 36*time.Second, func(c context.Context) (string, error) {
		if drama.VIP != nil && *drama.VIP {
			unknown = "样本需要来源会员授权"
			return unknown, nil
		}
		detail, err := engine.nativeDetail(c, drama)
		if err != nil {
			return "", err
		}
		value, ok := detail.(map[string]any)
		if !ok {
			return "", errors.New("detail shape invalid")
		}
		chapters, _ = value["chapters"].([]Chapter)
		if len(chapters) == 0 {
			return "", errors.New("no episodes")
		}
		chapter, index, found := Chapter{}, 0, false
		for i, candidate := range chapters {
			if !candidate.VIP {
				chapter, index, found = candidate, i+1, true
				break
			}
		}
		if !found {
			unknown = "分集需要来源会员授权"
			return unknown, nil
		}
		request := nativeInput{Action: "resolve", Drama: drama, Chapter: chapter, Index: index, Quality: 480, Force: true, PlaybackCacheScope: "repository-health-anonymous"}
		if err := engine.authorizeConfiguredSource(request); err != nil {
			return "", err
		}
		plan, err := engine.nativeResolve(c, request)
		if err != nil {
			return "", err
		}
		defer engine.nativeReleasePlayback(plan.Session)
		engine.mu.Lock()
		choice, ok := engine.playbacks[plan.Session]
		engine.mu.Unlock()
		if !ok || choice.index < 0 || choice.index >= len(choice.media) {
			return "", errors.New("missing selected media")
		}
		body, message, err := repositoryHealthSample(c, engine.downloader, choice.media[choice.index])
		if err != nil {
			return "", err
		}
		if message != "" {
			unknown = message
			return message, nil
		}
		if os.Getenv("YINGCHUAN_HEALTH_FFMPEG") == "" {
			unknown = "取流成功，缺少 FFmpeg 未解码"
			return unknown, nil
		}
		return "客户端取流及抽样首帧通过", repositoryHealthDecode(c, body)
	})
	if unknown != "" {
		outcome := result["playback"]
		outcome.Status = "unknown"
		result["playback"] = outcome
	}
	return result
}

func TestSourceHealthProbe(t *testing.T) {
	if os.Getenv("YINGCHUAN_HEALTH_RUN") != "1" {
		t.Fatal("native health runner requires explicit mode")
	}
	var input repositoryHealthInput
	decoder := json.NewDecoder(io.LimitReader(os.Stdin, 2<<20))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&input) != nil {
		t.Fatal("invalid native health request")
	}
	engine, err := newNativeEngine(t.TempDir())
	if err != nil {
		t.Fatal("native health initialization failed")
	}
	defer engine.downloads.close()
	defer func() {
		if engine.stream != nil {
			engine.stream.server.Close()
		}
	}()
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.Proxy = nil
	transport.DialContext = repositoryHealthPublicDial
	transport.ResponseHeaderTimeout = 8 * time.Second
	browser := newHuangguoBrowserTransport(transport, engine.downloader)
	browser.newClient = func(proxy string) (browserHTTPClient, error) {
		if proxy != "" {
			return nil, errors.New("native health does not use external proxy credentials")
		}
		return tlsclient.NewHttpClient(tlsclient.NewNoopLogger(), tlsclient.WithClientProfile(profiles.Chrome_150), tlsclient.WithRandomTLSExtensionOrder(),
			tlsclient.WithDisableHttp3(), tlsclient.WithNotFollowRedirects(), tlsclient.WithTimeoutSeconds(12), tlsclient.WithCookieJar(tlsclient.NewCookieJar()), tlsclient.WithDialContext(repositoryHealthPublicDial))
	}
	defer browser.CloseIdleConnections()
	engine.downloader.client.Transport = &repositoryHealthTransport{base: browser}
	previousRedirect := engine.downloader.client.CheckRedirect
	engine.downloader.client.CheckRedirect = func(next *http.Request, via []*http.Request) error {
		if len(via) > 0 && via[len(via)-1].URL.Scheme == "https" && next.URL.Scheme != "https" {
			return errors.New("native health refuses TLS downgrade")
		}
		if previousRedirect != nil {
			return previousRedirect(next, via)
		}
		return nil
	}
	engine.downloader.client.Timeout = 12 * time.Second
	engine.downloader.cfg.Retries = 1
	ctx, cancel := context.WithTimeout(context.Background(), 70*time.Second)
	defer cancel()
	ctx = context.WithValue(ctx, backgroundCatalogKey{}, true)
	body, err := json.Marshal(repositoryHealthProbe(ctx, engine, input))
	if err != nil {
		t.Fatal("native health result serialization failed")
	}
	fmt.Printf("YINGCHUAN_HEALTH %s\n", body)
}

type repositoryHealthFixtureTransport func(*http.Request) (*http.Response, error)

func (transport repositoryHealthFixtureTransport) RoundTrip(request *http.Request) (*http.Response, error) {
	return transport(request)
}

func TestRepositoryHealthSyntheticNativeFlow(t *testing.T) {
	executable, err := exec.LookPath("ffmpeg")
	if err != nil {
		t.Fatal("synthetic native flow requires FFmpeg")
	}
	t.Setenv("YINGCHUAN_HEALTH_FFMPEG", executable)
	command := exec.Command(executable, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:r=10", "-t", "2", "-c:v", "mpeg2video", "-threads", "1", "-f", "mpegts", "pipe:1")
	sample, err := command.Output()
	if err != nil {
		t.Fatal("synthetic video generation failed")
	}
	engine, err := newNativeEngine(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer engine.downloads.close()
	defer func() {
		if engine.stream != nil {
			engine.stream.server.Close()
		}
	}()
	coverHeads, searchCalls, mediaCalls := 0, 0, 0
	fixture := repositoryHealthFixtureTransport(func(request *http.Request) (*http.Response, error) {
		response := &http.Response{StatusCode: 200, Header: http.Header{}, Request: request}
		var payload any
		switch request.URL.Hostname() {
		case "cover.native.example.test":
			if request.Method != http.MethodHead {
				t.Error("native flow requested an image body")
			}
			coverHeads++
			response.Header.Set("Content-Type", "image/jpeg")
			response.Body = io.NopCloser(strings.NewReader(""))
			return response, nil
		case "media.native.example.test":
			mediaCalls++
			response.Header.Set("Content-Type", "video/mp2t")
			response.Body = io.NopCloser(bytes.NewReader(sample))
			if strings.HasSuffix(request.URL.Path, ".m3u8") {
				response.Header.Set("Content-Type", "application/vnd.apple.mpegurl")
				response.Body = io.NopCloser(strings.NewReader("#EXTM3U\n#EXTINF:2,\nsegment.ts\n#EXT-X-ENDLIST\n"))
			}
			return response, nil
		case "api.native.example.test":
			row := map[string]any{"id": 7, "title": "Synthetic native title", "cover": "https://cover.native.example.test/poster.jpg"}
			switch request.URL.Path {
			case "/sorani-cms/api/video", "/sorani-cms/api/video/search":
				if strings.HasSuffix(request.URL.Path, "/search") {
					searchCalls++
					if request.URL.Query().Get("keyword") != "Synthetic native title" {
						t.Error("search did not use sampled title")
					}
				}
				payload = map[string]any{"records": []any{row}, "total": 1}
			case "/sorani-cms/api/video/7":
				row["episodes"] = []any{map[string]any{"id": 11, "episodeOrder": 1, "enabled": true}}
				payload = row
			case "/sorani-cms/api/video/episode/11/play":
				payload = map[string]any{"canPlay": true, "playUrl": "https://media.native.example.test/index.m3u8"}
			default:
				t.Errorf("unexpected native endpoint %s", request.URL.Path)
				return nil, errors.New("unexpected synthetic endpoint")
			}
		default:
			t.Error("native flow left the synthetic transport")
			return nil, errors.New("unexpected synthetic host")
		}
		body, _ := json.Marshal(map[string]any{"code": 200, "data": payload})
		response.Header.Set("Content-Type", "application/json")
		response.Body = io.NopCloser(bytes.NewReader(body))
		return response, nil
	})
	engine.downloader.client.Transport = &repositoryHealthTransport{base: fixture}
	site := json.RawMessage(`{"name":"Synthetic native","api":"https://native.example.test","adapter":"sorani","native":{"version":1,"apiUrl":"https://api.native.example.test/sorani-cms/api","allowedHosts":["native.example.test","api.native.example.test","cover.native.example.test","media.native.example.test"],"playbackLine":"anime_jp_m3u8"}}`)
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	result := repositoryHealthProbe(ctx, engine, repositoryHealthInput{Version: 1, Key: "sorani", Site: site})
	for field, outcome := range result {
		if outcome.Status != "ok" {
			t.Errorf("%s: %+v", field, outcome)
		}
	}
	if coverHeads != 1 || searchCalls != 1 || mediaCalls < 2 {
		t.Fatalf("native visible protocol steps missing: HEAD=%d search=%d media=%d", coverHeads, searchCalls, mediaCalls)
	}
}

func TestRepositoryHealthInventoryConfiguration(t *testing.T) {
	root := os.Getenv("YINGCHUAN_HEALTH_SUBSCRIPTIONS")
	if root == "" {
		t.Fatal("explicit subscription directory is required")
	}
	for _, group := range []string{"film-tv", "short-drama", "animation", "unknown"} {
		entries := map[string]json.RawMessage{}
		adapters := []string{}
		body, err := os.ReadFile(filepath.Join(root, group+".json"))
		if err != nil {
			t.Fatal(err)
		}
		var document struct {
			Sites map[string]json.RawMessage `json:"api_site"`
		}
		if json.Unmarshal(body, &document) != nil {
			t.Fatal("invalid subscription")
		}
		for key, raw := range document.Sites {
			entries[key] = raw
			var site struct {
				Adapter string `json:"adapter"`
			}
			if json.Unmarshal(raw, &site) != nil {
				t.Fatal("invalid site")
			}
			if site.Adapter != "" {
				if !nativeOptionalSource(site.Adapter) {
					t.Fatal("built-in source present in repository")
				}
				adapters = append(adapters, site.Adapter)
			}
		}
		engine, err := newNativeEngine(t.TempDir())
		if err != nil {
			t.Fatal(err)
		}
		defer engine.downloads.close()
		engine.downloader.client.Transport = repositoryHealthFixtureTransport(func(*http.Request) (*http.Response, error) {
			t.Error("configuration validation accessed network")
			return nil, errors.New("network blocked")
		})
		config, _ := json.Marshal(map[string]any{"cache_time": 7200, "api_site": entries})
		payload, _ := json.Marshal(map[string]any{"text": string(config), "revision": 0})
		_, err = engine.generalMedia(context.Background(), nativeInput{Command: "apply", GeneralMedia: payload, GeneralMediaAccess: nativeGeneralMediaAccess{Admin: true, Unlocked: true}})
		if err != nil {
			t.Fatal(err)
		}
		for _, adapter := range adapters {
			if err := engine.authorizeConfiguredSource(nativeInput{Action: "catalog", Source: adapter}); err != nil {
				t.Fatal(adapter, err)
			}
		}
		t.Logf("validated %s: %d JSON entries and %d native bindings using the pinned client parser", group, len(entries), len(adapters))
	}
}

func TestRepositoryHealthAddressBoundaries(t *testing.T) {
	for _, raw := range []string{"127.0.0.1", "10.0.0.1", "100.64.0.1", "169.254.169.254", "192.0.2.1", "198.18.0.1", "240.0.0.1", "::1", "::ffff:127.0.0.1", "2001:db8::1", "fe80::1"} {
		if repositoryHealthPublicIP(net.ParseIP(raw)) {
			t.Errorf("accepted non-public address %s", raw)
		}
	}
	for _, raw := range []string{"8.8.8.8", "1.1.1.1", "2001:4860:4860::8888"} {
		if !repositoryHealthPublicIP(net.ParseIP(raw)) {
			t.Errorf("rejected public address %s", raw)
		}
	}
}

type repositoryHealthBodyTrap struct{ read, closed bool }

func (body *repositoryHealthBodyTrap) Read([]byte) (int, error) {
	body.read = true
	return 0, errors.New("image body must not be read")
}
func (body *repositoryHealthBodyTrap) Close() error { body.closed = true; return nil }

func TestRepositoryHealthImagePolicy(t *testing.T) {
	body := &repositoryHealthBodyTrap{}
	calls := 0
	transport := &repositoryHealthTransport{base: repositoryHealthFixtureTransport(func(request *http.Request) (*http.Response, error) {
		calls++
		return &http.Response{StatusCode: 200, Header: http.Header{"Content-Type": []string{"image/jpeg"}}, Body: body, Request: request}, nil
	})}
	request, _ := http.NewRequest(http.MethodGet, "https://fixture.example/opaque", nil)
	if _, err := transport.RoundTrip(request); !errors.Is(err, repositoryHealthImage) {
		t.Fatal("opaque image response was not blocked")
	}
	if body.read || !body.closed || calls != 1 {
		t.Fatal("image policy read the body or leaked response")
	}
	request, _ = http.NewRequest(http.MethodGet, "https://fixture.example/cover.jpg", nil)
	if _, err := transport.RoundTrip(request); !errors.Is(err, repositoryHealthImage) || calls != 1 {
		t.Fatal("known image GET reached transport")
	}
	request, _ = http.NewRequest(http.MethodHead, "https://fixture.example/cover.jpg", nil)
	response, err := transport.RoundTrip(request)
	if err != nil || calls != 2 {
		t.Fatal("cover HEAD did not reach transport")
	}
	response.Body.Close()
	if body.read {
		t.Fatal("HEAD read an image body")
	}
}
