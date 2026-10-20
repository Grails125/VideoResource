# VideoResource

## 259 当前108项审计与公共接口备选（2026-10-21）

[逐项阶段与线路矩阵](audits/source-audit259-status.json)覆盖5个内置来源及当前103个导入来源。45个有成人标识或restricted身份的项目只做静态与HEAD健康检查，不取媒体；另有2项因既有成人参考或实际成人分类停在元数据边界，未取媒体。其余按实际接口检查目录、分类、搜索、详情和返回线路。分类元数据共返回1789项，其中29项随实际成人分类来源停止取样，其余逐项检查1760个真实分类首屏；实际返回45条线路分别记录解析、起播与前缀下载结果，28条确认解码起播、27条取得有界下载前缀。错误、拒绝、超时、未支持与未验证均保留，不将108项写成全通过。

封面只检查HEAD响应与URL元数据，HEAD成功不等于图片显示或解码通过。清单分片若触发图片地址保护，保持未验证，不判成海报错误或放宽图片正文限制。媒体只取必要key/init、少量分片或Range前缀，不下载整部视频，不绕过验证码、权限、登录或加密授权。检查为Windows宿主原生核心及隔离本地流的libmpv小样本，不代表安装版Flutter界面、Android/TV或物理掌机验收。

8个上游公共候选经过本客户端消费者检查，其中1项在两轮有界小样本中均确认起播与下载前缀，并逐项检查42个分类首屏。仅该项收入独立可选的[public-alternatives259.json](public-alternatives259.json)，不合入默认订阅，不覆盖现有个人配置；导入仍只新增。它是本环境重复取样可用的备选，不承诺全局更快或永久可用，也不能替代已有来源的全部分类/线路。其他候选的403、404与消费者拒绝留在矩阵，不添加占位配置。

## 原生适配资料（任务243）

短剧汇 `0.0.163+242` 保留 B站、红果、影视、影视2、奈飞五个内置来源。其余11个原生适配器的名称、说明、入口、API、备用域、分类及线路资料由本仓库配置提供，客户端只保留适配方法、稳定来源身份和权限规则。2026-10-21核对时，`main` 已包含 `codex/tvbox-jianpian` 的全部历史提交，且另有2个提交；本轮审计与备选资料位于 `codex/source-audit259`，不自动合入 `main`。

- [native.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/native.json)：原10项可选原生配置，内容与本分支 `config.json` 一致。
- [tencent.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/tencent.json)：独立腾讯原生配置。
- [integrated.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/integrated.json)：原50项合集，保留原来源和稳定键，仅为其中10项可选原生配置补齐资料。

每项 `api` 是站点根，`native.version` 为 `1`。可选字段包括独立 `apiUrl` / `cdnUrl`、按角色组织的 `endpoints`、备用 `mirrors`、`allowedHosts` / `allowedSuffixes`、旧输入 `aliases`、分类 `categories`、`playbackLine`、发现入口 `transitSites` / `seedWords`、`generatedMirrorSuffix`、`description` / `warning`。封面引用来源由 `endpoints.coverReferer` 与 `coverRefererHosts` 配套限定。角色路径与站点根不可混用；资料缺失不会回退到客户端内置旧地址。

配置导入仅新增，稳定键冲突会保留现有项，重新订阅不会暗中覆盖用户配置。旧记录补充或更新 `native` 资料时，请使用明确编辑或规则更新流程；编辑原生项时将对应的 `native` 对象放入“站源资料 JSON”，不要把整份订阅文档放进去。旧客户端未传 `native` 的编辑保留已有资料，禁用状态和权限不会因补资料自动改变。

`archive/source_repository/` 保存从客户端移出的94个历史文本文件，其中86个 Kazumi JSON。归档用于追溯，不是当前可安装的原生配置，也不恢复已退休的脚本执行器。配置迁移和文本解析检查不等于站源健康或实际媒体播放验收。

短剧汇在线源配置仓库，提供十个可选原生来源的订阅配置。

## 使用方法

在应用「设置 → 站源管理 → 添加 → 配置订阅」选择「VideoResource 源仓库」，或填写以下订阅地址，获取后检查预览再确认：

```text
https://raw.githubusercontent.com/Grails125/VideoResource/main/config.json
```

配置安装仍需客户端支持对应的原生适配器，不会自动解锁来源，也不支持通过填写任意网站地址自动接入。

## 配置文件

| 配置                                                                                                     | 内容                                     |
| -------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| [config.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/config.json)                 | 默认订阅，包含十个可选原生来源           |
| [plugin20261016.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/plugin20261016.json) | 2026-10-16新增配置 |

配置中的 `cache_time` 为 `7200`；`api_site` 按来源稳定键组织，每个条目包含显示名称 `name`、站点地址 `api` 和客户端适配器标识 `adapter`。稳定键直接使用 `hanxiaoquan`、`sorani` 等名称。

## 来源清单

| 来源   | 稳定键 / 适配器标识 |
| ------ | ------------------- |
| 韩小圈 | `hanxiaoquan`     |
| 鬼片   | `guipian`         |
| 青空   | `sorani`          |

配置收录不代表站点当前可播放，实际可用性取决于站点状态及客户端适配器。本仓库不存账号、Cookie、私钥或设备配置。

## 分类可选订阅

短剧汇`0.0.149+228`起直接内置影视2，默认位于B站、红果、影视之后，无需导入或来源解锁。下方荐片配置及合集中的相同条目继续兼容旧客户端；新客户端保留原配置记录并使用内置入口，不增加重复来源。请勿将荐片H5网页首页作为普通JSON／XML采集接口；旧误配会提示使用内置影视2，不放宽XML解析校验。

| 配置 | 用途 |
| --- | --- |
| [integrated.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/integrated.json) | 50项合集：原生10＋影视2原生适配1＋JSON28＋XML11，一次预览确认共同安装 |
| [jianpian.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/jianpian.json) | 影视2原生适配配置，需要支持`jianpian`适配器的新客户端；旧默认配置不追加此项 |
| [tvbox-json.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/tvbox-json.json) | TVBox type1标准JSON采集接口 |
| [tvbox-xml.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/tvbox-xml.json) | TVBox type0标准XML采集接口 |
| [tvbox-pending.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/tvbox-pending.json) | 21项待验证配置，全部默认禁用；仅供手动选择，不作为快捷推荐 |

短剧汇`0.0.148+227`源码为影视2增加发现页封面目录、推荐／电影／电视剧／动漫／综艺分类及连续分页，保留关键词搜索；旧`0.0.147+226`仍仅支持搜索。已安装的`jianpian`配置无需修改或重新导入，能力以客户端实际版本为准。荐片H5独立短剧入口使用另一套ID与播放消费者，当前未接入，不混用普通影视详情；`jianpian://`、荐片账号及付费授权仍未实现。目录元数据成功不代表图片或媒体实播已验收。

TVBox配置固定参考`hebijunge/tvbox-config`提交`7d5a8d531cd8be71c1299c054a4234b0302b4a1c`，按API规范化去重，保留名称和语义查询参数。上游adult.json明确归类的API／主机排除；名称存在疑问的条目另按待确认保守排除，不将名称当作已确认内容证据。分类文件按接口协议组织，不代表影视题材分类或全部来源内容性质已核实。

JSON／XML配置只面向客户端支持的标准采集接口及标准直连媒体，不包含JAR、JS、spider、type4或需要额外扩展、请求头、播放前缀的配置。原103项配置保持不变；分类订阅与旧配置可能有相同接口，安装前查看预览。上游healthy等标签不代表本客户端已实播，目录响应也不等于媒体可播；实际仍受站点状态、权限和客户端协议支持限制。

本轮最终主分类订阅保留28个JSON及11个XML接口（共39）：通过应用实际core parser的目录请求与转换检查，不表示媒体实播通过。此前初步结构检查的49项中，39项通过本轮实际消费者检查，10项未通过本轮保守检查，不能据此断定永久失效；它们与原11项待验证配置共同保存在`tvbox-pending.json`，共21项，逐项设置`disabled:true`，不作为快捷推荐。

目录分类明确含成人标记的14个新增JSON接口已剔除，包括未列入上游adult清单但本次目录给出明确标记的接口；原103项配置不在本轮批量修改范围。`integrated.json`按稳定键合并原`config.json`的10项原生来源、影视2原生适配1项及主分类39项，共50项，无键冲突。已有单订阅安装采用替换语义，想让这些来源共存时一次选择合集、检查预览后确认；不依次安装分类订阅来冒充合集。旧`config.json`仍保持原样，影视2需要支持`jianpian`的新客户端。

这些分类文件按实际JSON／XML协议组织；影视、动漫、短剧等站内分类以各API实际返回为准，由客户端动态展示，不从来源名称或文件名猜测。目录检查只请求`ac=list,pg=1`，未请求图片、播放清单或媒体，未验证用户授权与实际播放。8秒socket超时不等于严格请求总时限，本轮最长完整请求约15.5秒。

任务244逐源审计见[audits/plugin20261016-status.json](audits/plugin20261016-status.json)：原配置93项逐项保留，首次18项取得有界公开样本解码确认；明确成人引用或实际成人分类的25项未采媒体，其余失败与未确认按阶段记录，不据此删除来源。播放只验证少量分片，下载只验证首段处理链，不代表全片、完整离线或设备界面验收。封面仅HEAD元数据，图片正文读取为0。

初轮、16项诊断补采、分集编号夹具修正后补采分别记录，不把重复请求或后续单项成功累加成初轮通过数。黄果视频不在原93项中，单独记录：本轮自动代理路径首页返回Cloudflare访问拒绝页面，未获取媒体；没有改用户代理或绕过访问限制。审计文件仅保留来源标识、状态、时间、计数和摘要，不含影片名称、媒体地址或密钥；状态具有时效性，不构成上游长期可用承诺。

初轮封面HEAD限3秒，40次超时、1次EOF，不能据此认定封面失效。另以12秒、最多3来源并发补测41项：39项实际发出HEAD，36项200、1项403、1项404、1项EOF；2项目录重取失败未取得封面。仅响应元数据，不读取图片正文，200也不代表已验证图片解码；405若出现仅表示不支持HEAD。本轮没有405，补测不请求媒体正文，独立记录在`coverFollowUp`。

### 259定向失败补查

公开审计JSON另列 `followupDiagnostics`，原108入口、1760分类首屏、45条线路的历史结果与覆盖计数保留。红果漫剧／AI剧实际出现HTTP200空body，AI小样本曾返回18条后再次为空；ryzyw三分类明确返回code=1、list=null、pagecount=0、total=0，客户端已按严格空终态修复，后续仅记空结果。其他失败区分网页响应、非JSON对象、API失败码1002、HTTP503、HTTPS协议不符、HTTP/2 INTERNAL_ERROR和无公开直连分集。

奈飞／新浪的后续1080p小样本与五条影视2线路的前缀检查独立记录，不把不同时间或无法核同一剧集／线路的成功覆盖为原全量通过。旧探针未保留的错误细节和选中线路身份仍明确未知。来源15发现成人分类后仅静态核对、未再发网络请求；45项静态限制与另外15／43／65的后续只查metadata边界分别记录。封面HEAD不等于显示或解码验证。
