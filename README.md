# VideoResource

## 原生适配资料（任务243）

短剧汇保留 B站、红果、影视、影视2、奈飞五个内置来源。其余13个可选原生适配器的名称、说明、入口、API、备用域、分类及线路资料由本仓库配置提供，客户端只保留适配方法、稳定来源身份和权限规则。默认订阅包含12项，腾讯另有独立配置；当前配置维护于 `main`。

- [native.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/native.json)：12项可选原生配置，内容与 `config.json` 一致，包含禁果和禁果短剧。
- [tencent.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/tencent.json)：独立腾讯原生配置。
- [integrated.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/integrated.json)：52项合集，包含12项可选原生配置、影视2与39项JSON／XML采集配置，保留原来源和稳定键。

每项 `api` 是站点根，`native.version` 为 `1`。可选字段包括独立 `apiUrl` / `cdnUrl`、按角色组织的 `endpoints`、备用 `mirrors`、`allowedHosts` / `allowedSuffixes`、旧输入 `aliases`、分类 `categories`、`playbackLine`、发现入口 `transitSites` / `seedWords`、`generatedMirrorSuffix`、`description` / `warning`。封面引用来源由 `endpoints.coverReferer` 与 `coverRefererHosts` 配套限定。角色路径与站点根不可混用；资料缺失不会回退到客户端内置旧地址。

配置导入仅新增，稳定键冲突会保留现有项，重新订阅不会暗中覆盖用户配置。旧记录补充或更新 `native` 资料时，请使用明确编辑或规则更新流程；编辑原生项时将对应的 `native` 对象放入“站源资料 JSON”，不要把整份订阅文档放进去。旧客户端未传 `native` 的编辑保留已有资料，禁用状态和权限不会因补资料自动改变。

`archive/source_repository/` 保存从客户端移出的94个历史文本文件，其中86个 Kazumi JSON。归档用于追溯，不是当前可安装的原生配置，也不恢复已退休的脚本执行器。配置迁移和文本解析检查不等于站源健康或实际媒体播放验收。

短剧汇在线源配置仓库，提供十二个可选原生来源的订阅配置。

## 使用方法

在应用「设置 → 站源管理 → 添加 → 配置订阅」选择「VideoResource 源仓库」，或填写以下订阅地址，获取后检查预览再确认：

```text
https://raw.githubusercontent.com/Grails125/VideoResource/main/config.json
```

配置安装仍需客户端支持对应的原生适配器，不会自动解锁来源，也不支持通过填写任意网站地址自动接入。

## 配置文件

| 配置                                                                                                     | 内容                                     |
| -------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| [config.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/config.json)                 | 默认订阅，包含十二个可选原生来源           |
| [plugin20261016.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/plugin20261016.json) | 2026-10-16新增配置 |

配置中的 `cache_time` 为 `7200`；`api_site` 按来源稳定键组织，每个条目包含显示名称 `name`、站点地址 `api` 和客户端适配器标识 `adapter`。稳定键直接使用 `hanxiaoquan`、`sorani` 等名称。

## 来源清单

| 来源 | 稳定键 / 适配器标识 |
| --- | --- |
| 韩小圈 | `hanxiaoquan` |
| 鬼片 | `guipian` |
| 青空 | `sorani` |
| 黄豆 | `huangdou` |
| 剧果 | `huangju` |
| 野果 | `yeguo` |
| 帝果 | `dsd` |
| 黄果视频 | `huangguo-video` |
| 黄果AI | `huangguoai` |
| 黄果旧版 | `cloudfront` |
| 禁果 | `jinguo` |
| 禁果短剧 | `jinguoduanju` |

禁果和禁果短剧使用两个独立适配器与来源身份，入口、API、备用域和元数据角色地址参考 `Xanerix/guoapp` 提交 `219405676fd6da4d4b05e99b7ad4a2d1814cd38e`，仅迁入配置资料。本次验证配置解析、来源身份、分类ID和域名边界，没有请求站源图片或进行真实站点播放验证。已安装订阅请重新获取预览并确认新增；已有同键项继续保留，更新已有项需明确确认。

黄豆配置同步6个域名池入口，参考 `Xanerix/guoapp` 提交 `36c9eb9c72c9c8ae0ba8e46331a8b6c0268671b9`；主入口为 ferncider.cc，其余5个按配置顺序备用。2026-11-07本机通过当前客户端协议逐一请求有界目录元数据，6个均返回可解码资料；未请求图片或媒体，不代表全站播放通过。已安装的黄豆资料需要预览订阅更新并确认，普通重复导入保留个人旧配置。

配置收录不代表站点当前可播放，实际可用性取决于站点状态及客户端适配器。本仓库不存账号、Cookie、私钥或设备配置。

## 分类可选订阅

短剧汇`0.0.149+228`起直接内置影视2，默认位于B站、红果、影视之后，无需导入或来源解锁。下方荐片配置及合集中的相同条目继续兼容旧客户端；新客户端保留原配置记录并使用内置入口，不增加重复来源。请勿将荐片H5网页首页作为普通JSON／XML采集接口；旧误配会提示使用内置影视2，不放宽XML解析校验。

| 配置 | 用途 |
| --- | --- |
| [integrated.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/integrated.json) | 52项合集：原生12＋影视2原生适配1＋JSON28＋XML11，一次预览确认共同安装 |
| [jianpian.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/jianpian.json) | 影视2原生适配配置，需要支持`jianpian`适配器的新客户端；旧默认配置不追加此项 |
| [tvbox-json.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/tvbox-json.json) | TVBox type1标准JSON采集接口 |
| [tvbox-xml.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/tvbox-xml.json) | TVBox type0标准XML采集接口 |
| [gnoix-api.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/gnoix-api.json) | Gnoix API 精选15项，复用既有稳定键，茅台和如意继续默认禁用 |
| [tvbox-pending.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/tvbox-pending.json) | 21项待验证配置，全部默认禁用；仅供手动选择，不作为快捷推荐 |

短剧汇`0.0.148+227`源码为影视2增加发现页封面目录、推荐／电影／电视剧／动漫／综艺分类及连续分页，保留关键词搜索；旧`0.0.147+226`仍仅支持搜索。已安装的`jianpian`配置无需修改或重新导入，能力以客户端实际版本为准。荐片H5独立短剧入口使用另一套ID与播放消费者，当前未接入，不混用普通影视详情；`jianpian://`、荐片账号及付费授权仍未实现。目录元数据成功不代表图片或媒体实播已验收。

TVBox配置固定参考`hebijunge/tvbox-config`提交`7d5a8d531cd8be71c1299c054a4234b0302b4a1c`，按API规范化去重，保留名称和语义查询参数。上游adult.json明确归类的API／主机排除；名称存在疑问的条目另按待确认保守排除，不将名称当作已确认内容证据。分类文件按接口协议组织，不代表影视题材分类或全部来源内容性质已核实。

JSON／XML配置只面向客户端支持的标准采集接口及标准直连媒体，不包含JAR、JS、spider、type4或需要额外扩展、请求头、播放前缀的配置。原103项配置保持不变；分类订阅与旧配置可能有相同接口，安装前查看预览。上游healthy等标签不代表本客户端已实播，目录响应也不等于媒体可播；实际仍受站点状态、权限和客户端协议支持限制。

本轮最终主分类订阅保留28个JSON及11个XML接口（共39）：通过应用实际core parser的目录请求与转换检查，不表示媒体实播通过。此前初步结构检查的49项中，39项通过本轮实际消费者检查，10项未通过本轮保守检查，不能据此断定永久失效；它们与原11项待验证配置共同保存在`tvbox-pending.json`，共21项，逐项设置`disabled:true`，不作为快捷推荐。

目录分类明确含成人标记的14个新增JSON接口已剔除，包括未列入上游adult清单但本次目录给出明确标记的接口；原103项配置不在本轮批量修改范围。`integrated.json`按稳定键合并`config.json`的12项原生来源、影视2原生适配1项及主分类39项，共52项，无键冲突。导入订阅仅新增，已有同键项和个人配置继续保留；合集可一次预览并确认新增全部来源。已有来源配置保持原样；默认订阅新增禁果与禁果短剧，需客户端支持 `jinguo`／`jinguoduanju` 原生适配器。影视2需要支持 `jianpian` 的客户端。

这些分类文件按实际JSON／XML协议组织；影视、动漫、短剧等站内分类以各API实际返回为准，由客户端动态展示，不从来源名称或文件名猜测。目录检查只请求`ac=list,pg=1`，未请求图片、播放清单或媒体，未验证用户授权与实际播放。8秒socket超时不等于严格请求总时限，本轮最长完整请求约15.5秒。

任务244逐源审计见[audits/plugin20261016-status.json](audits/plugin20261016-status.json)：原配置93项逐项保留，首次18项取得有界公开样本解码确认；明确成人引用或实际成人分类的25项未采媒体，其余失败与未确认按阶段记录，不据此删除来源。播放只验证少量分片，下载只验证首段处理链，不代表全片、完整离线或设备界面验收。封面仅HEAD元数据，图片正文读取为0。

初轮、16项诊断补采、分集编号夹具修正后补采分别记录，不把重复请求或后续单项成功累加成初轮通过数。黄果视频不在原93项中，单独记录：本轮自动代理路径首页返回Cloudflare访问拒绝页面，未获取媒体；没有改用户代理或绕过访问限制。审计文件仅保留来源标识、状态、时间、计数和摘要，不含影片名称、媒体地址或密钥；状态具有时效性，不构成上游长期可用承诺。

初轮封面HEAD限3秒，40次超时、1次EOF，不能据此认定封面失效。另以12秒、最多3来源并发补测41项：39项实际发出HEAD，36项200、1项403、1项404、1项EOF；2项目录重取失败未取得封面。仅响应元数据，不读取图片正文，200也不代表已验证图片解码；405若出现仅表示不支持HEAD。本轮没有405，补测不请求媒体正文，独立记录在`coverFollowUp`。

## Gnoix API 精选订阅

[gnoix-api.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/gnoix-api.json) 对照 [Gnoix rules.json](https://gnoix.277722.xyz/rules.json) 的20261102快照整理。33项中，13个API与既有接口同址，另2项已核对目录请求等价；这15项直接复用本仓库的稳定键、地址、名称及禁用状态，茅台和如意仍为待验证禁用项。已导入旧订阅的同键项继续保留；新版客户端也按标准采集接口去重，不覆盖个人名称和配置。

非凡、最大、索尼、天涯、无尽的5个不同入口尚未证明内容身份一致，本订阅未新增或替换这些地址；天翼返回停放网页，未收录。12个JS规则不执行，也不作为API导入；可选原生来源继续使用对应原生订阅。这是兼容子集，不是新增15个独立提供方，也不表示15项均已实播或内容范围已核实。未读取图片或播放媒体。
