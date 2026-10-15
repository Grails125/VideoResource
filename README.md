# VideoResource

短剧汇在线源仓库。当前配置结构要求客户端 **0.0.123+202** 或后续兼容版本，旧200／201客户端不支持本次嵌套线路结构。

所有版本只内置红果、B站和看剧AI，其余已支持的十个来源通过配置安装。外层稳定键直接使用 `hanxiaoquan`、`sorani` 等名称，无需 `native:` 或 `kazumi:` 前缀；`adapter` 和规则字段决定实际解析方式，旧前缀兼容映射到原身份。

在应用「设置 → 站源管理 → 添加 → 配置订阅」点击「VideoResource 源仓库」，或填写以下地址，获取后检查预览再确认。保留原有来源ID、个人顺序、隐藏、权限、观看和下载资料，不会自动解锁来源。

| 配置 | 内容 |
| --- | --- |
| [config.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/config.json) | 十个可选来源，青空内含16条当前规则线路 |
| [native.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/native.json) | 与默认扩展包相同，保留原订阅地址 |
| [kazumi.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/kazumi.json) | 仅青空配置及16条当前规则线路 |
| [all.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/all.json) | 青空86条规则线路，70条上游废弃规则默认禁用 |
| [archive.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/archive.json) | 青空70条废弃线路，全部禁用 |

十个可选来源为韩小圈、鬼片、青空、黄豆、剧果、野果、帝果、黄果视频、黄果AI、黄果旧版。来源仍需对应的客户端适配器，不承诺任意网站自动接入。

规则放在青空的 `lines` 内，不再显示为独立站源。青空首页沿用真实目录；关键词搜索调用已启用线路并保留规则身份。播放器选择备用线路时才核验完整同名作品与对应分集；同名歧义、相似标题或匿名分集不能强行映射，可先在青空搜索中选择具体结果。原始规则JSON、数组和 `kazumi://` 分享链接也会归入青空。

规则来自 [Predidit/KazumiRules](https://github.com/Predidit/KazumiRules/tree/2fa4d28659f94e1eb52e7a38d79b7b9a5dcd605b)，固定提交 `2fa4d28659f94e1eb52e7a38d79b7b9a5dcd605b`，遵循 [MIT许可](LICENSE.kazumi.txt)。`kazumi/` 内86份原始JSON字节、SHA-256和废弃标记不变；`index.json` 是元数据索引，不是订阅入口。参考 [Kazumi固定源码](https://github.com/Predidit/Kazumi/tree/025dcb5c2f62db881382c72f191d08b49a9feb41) 独立适配协议，不复制GPL应用代码。

已用合成数据检查结构、导入回读、搜索、分集、换线与临时浏览器重试，**不代表86个网站实时可播**。站点改版、失效域名、登录、地区及站点授权仍可能使规则失效。未请求站源图片或视频。Android／Windows动态解析使用隔离临时浏览器，验证码需用户手动完成，不执行任意验证码脚本；真实设备行为仍待验收，iOS动态解析未接入。旧useWebview／useNativePlayer／useLegacyParser／adBlocker字段可回读，不切换成Kazumi的平台实现或启用猜测裁流。

广告自动跳过只使用明确广告标记及可靠时间轴，不猜测跳过正片。本仓库不存账号、Cookie、私钥或设备配置；上游公开客户端标识随原规则保留。
