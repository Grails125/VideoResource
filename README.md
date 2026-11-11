<p align="center"><img src="assets/brand-icon.svg" width="80" alt="映川 · 澄青川流精修 A 图标"></p>

# 映川 · 站源订阅

映川（YingChuan）的四份站源订阅，供客户端按分类选择导入。品牌标识统一使用澄青川流精修 A 的[深墨双青图标](assets/brand-icon.svg)与[可编辑主标识](assets/brand-logo.svg)。仓库只保留下表四个 JSON 文件，不提供旧批次、合集、索引或归档订阅。

| 分类 | 订阅地址 | 来源数 |
| --- | --- | ---: |
| 影视 | [subscriptions/film-tv.json](https://raw.githubusercontent.com/yingchuan-media/yingchuan-sources/main/subscriptions/film-tv.json) | 135 |
| 短剧 | [subscriptions/short-drama.json](https://raw.githubusercontent.com/yingchuan-media/yingchuan-sources/main/subscriptions/short-drama.json) | 6 |
| 动漫 | [subscriptions/animation.json](https://raw.githubusercontent.com/yingchuan-media/yingchuan-sources/main/subscriptions/animation.json) | 4 |
| 未知 | [subscriptions/unknown.json](https://raw.githubusercontent.com/yingchuan-media/yingchuan-sources/main/subscriptions/unknown.json) | 62 |

当前共 **207 项来源，全部默认启用**。成人标记来源及内容范围待确认的来源放在未知分类。分类依据配置中已有的信息，不代表当前已逐站在线核实内容或播放能力。

## 使用

在映川「设置 → 站源管理 → 添加 → 配置订阅」选择分类，或填写对应地址；读取预览后确认导入。更新已有配置时检查差异并明确确认，个人停用选择、来源身份、权限与观看下载资料由客户端管理。

四份订阅统一使用 `cache_time: 7200` 与 `api_site` 外层结构。普通采集接口使用 HTTP／HTTPS；原生来源通过客户端已支持的稳定适配器接入，可选配置使用 `native.version: 1`。仅使用客户端内置配置的影视2适配器可不提供 `native` 覆盖。

## 维护与校验

- 每个稳定来源键及接口身份只在一份订阅中维护。新增前检查键、适配器或规范化接口地址与独立详情配置，去重后追加到对应文件末尾；保留其他条目的内容和顺序。
- URL 去重仅统一主机大小写、默认端口、末尾斜线和 `ac=list`，保留其他查询参数、转义路径、HTTP／HTTPS 及独立详情配置。
- 所有发布来源默认启用；检查失败只记录结果，不自动禁用来源。不提交账号、Cookie、密钥、个人配置、媒体或站源图片。
- 不新增其他 JSON 文件。来源数量变化时同步更新本文及校验脚本中的分类数量；旧内容需要追溯时查看 Git 历史。

在仓库根目录执行：

```sh
python -B scripts/check_subscriptions.py
python -B scripts/test_check_subscriptions.py
```

校验器检查仅有四份订阅 JSON、外层结构与字段类型、各分类数量、稳定键和接口去重、公开 HTTP／HTTPS 地址、原生适配器身份及版本、默认启用状态与明确成人标记的分类。当前四份配置共 207 项通过这些离线检查，维护脚本的 18 项测试通过。

这些检查不请求站源图片、账号或媒体，也不等同于当前站点可用性、真实播放、完整原生配置行为或物理设备验收；来源访问条件仍由对应服务决定，不绕过 TLS、登录、付费、DRM 或访问拒绝。
