# VideoResource

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
| [integrated.json](https://raw.githubusercontent.com/Grails125/VideoResource/codex/tvbox-jianpian/integrated.json) | 50项合集：原生10＋影视2原生适配1＋JSON28＋XML11，一次预览确认共同安装 |
| [jianpian.json](https://raw.githubusercontent.com/Grails125/VideoResource/codex/tvbox-jianpian/jianpian.json) | 影视2原生适配配置，需要支持`jianpian`适配器的新客户端；旧默认配置不追加此项 |
| [tvbox-json.json](https://raw.githubusercontent.com/Grails125/VideoResource/codex/tvbox-jianpian/tvbox-json.json) | TVBox type1标准JSON采集接口 |
| [tvbox-xml.json](https://raw.githubusercontent.com/Grails125/VideoResource/codex/tvbox-jianpian/tvbox-xml.json) | TVBox type0标准XML采集接口 |
| [tvbox-pending.json](https://raw.githubusercontent.com/Grails125/VideoResource/codex/tvbox-jianpian/tvbox-pending.json) | 21项待验证配置，全部默认禁用；仅供手动选择，不作为快捷推荐 |

短剧汇`0.0.148+227`源码为影视2增加发现页封面目录、推荐／电影／电视剧／动漫／综艺分类及连续分页，保留关键词搜索；旧`0.0.147+226`仍仅支持搜索。已安装的`jianpian`配置无需修改或重新导入，能力以客户端实际版本为准。荐片H5独立短剧入口使用另一套ID与播放消费者，当前未接入，不混用普通影视详情；`jianpian://`、荐片账号及付费授权仍未实现。目录元数据成功不代表图片或媒体实播已验收。

TVBox配置固定参考`hebijunge/tvbox-config`提交`7d5a8d531cd8be71c1299c054a4234b0302b4a1c`，按API规范化去重，保留名称和语义查询参数。上游adult.json明确归类的API／主机排除；名称存在疑问的条目另按待确认保守排除，不将名称当作已确认内容证据。分类文件按接口协议组织，不代表影视题材分类或全部来源内容性质已核实。

JSON／XML配置只面向客户端支持的标准采集接口及标准直连媒体，不包含JAR、JS、spider、type4或需要额外扩展、请求头、播放前缀的配置。原103项配置保持不变；分类订阅与旧配置可能有相同接口，安装前查看预览。上游healthy等标签不代表本客户端已实播，目录响应也不等于媒体可播；实际仍受站点状态、权限和客户端协议支持限制。

本轮最终主分类订阅保留28个JSON及11个XML接口（共39）：通过应用实际core parser的目录请求与转换检查，不表示媒体实播通过。此前初步结构检查的49项中，39项通过本轮实际消费者检查，10项未通过本轮保守检查，不能据此断定永久失效；它们与原11项待验证配置共同保存在`tvbox-pending.json`，共21项，逐项设置`disabled:true`，不作为快捷推荐。

目录分类明确含成人标记的14个新增JSON接口已剔除，包括未列入上游adult清单但本次目录给出明确标记的接口；原103项配置不在本轮批量修改范围。`integrated.json`按稳定键合并原`config.json`的10项原生来源、影视2原生适配1项及主分类39项，共50项，无键冲突。已有单订阅安装采用替换语义，想让这些来源共存时一次选择合集、检查预览后确认；不依次安装分类订阅来冒充合集。旧`config.json`仍保持原样，影视2需要支持`jianpian`的新客户端。

这些分类文件按实际JSON／XML协议组织；影视、动漫、短剧等站内分类以各API实际返回为准，由客户端动态展示，不从来源名称或文件名猜测。目录检查只请求`ac=list,pg=1`，未请求图片、播放清单或媒体，未验证用户授权与实际播放。8秒socket超时不等于严格请求总时限，本轮最长完整请求约15.5秒。
