# VideoResource

短剧汇在线源仓库，适配客户端开发快照 **0.0.121+200** 及后续兼容版本。

在应用「设置 → 站源管理 → 添加 → 配置订阅」点击「VideoResource 源仓库」，或填写下面的 JSON 地址，获取后先检查导入预览再确认。订阅更新保留原有权限、配置修订校验和个人资料，不会自动解锁来源。

| 配置 | 内容 | 在线地址 |
| --- | --- | --- |
| 默认扩展包 | 3 个可选原生源及 16 个当前 Kazumi 规则 | [config.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/config.json) |
| 当前 Kazumi 规则 | 16 个未废弃规则 | [kazumi.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/kazumi.json) |
| 全量 Kazumi 规则 | 86 个规则，含 70 个默认禁用的废弃规则 | [all.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/all.json) |
| 可选原生源 | 韩小圈、鬼片、青空，保留原来源 ID | [native.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/native.json) |
| 废弃规则归档 | 70 个规则，默认禁用 | [archive.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/archive.json) |

应用默认入口只保留红果、看剧AI、B站；以上配置需要用户主动导入。单份原始规则位于 `kazumi/`，客户端也接受原始 JSON、规则数组和 `kazumi://` 分享链接。`index.json` 是版本、数量和 SHA-256 索引，不是配置订阅入口。

规则来自 [Predidit/KazumiRules](https://github.com/Predidit/KazumiRules/tree/2fa4d28659f94e1eb52e7a38d79b7b9a5dcd605b)，固定提交 `2fa4d28659f94e1eb52e7a38d79b7b9a5dcd605b`，遵循 [上游 MIT 许可](LICENSE.kazumi.txt)。原始规则字节与废弃标记保留。参考 [Kazumi](https://github.com/Predidit/Kazumi/tree/025dcb5c2f62db881382c72f191d08b49a9feb41) 的字段和协议独立实现客户端适配，不复制其 GPL 应用代码。

86 份规则已通过结构解析和导入／回读合成检查；XPath/API 搜索、章节映射、静态播放解析和动态解析会话另有合成用例。**这不是 86 个站点实时可播放的证明。** 废弃域名、站点改版、登录、地区与站点自身授权限制仍可能使规则不可用。未请求或验证站源图片、视频。

动态解析接入 Android/Windows 临时浏览器，验证码需用户手动完成，不执行规则中的任意验证码脚本；实际设备行为待验证。iOS 动态解析未接入，HTTP 旧页面、blob/MSE 导出和 DRM 不属于当前支持范围。规则中的旧 useWebview/useNativePlayer/useLegacyParser/adBlocker 字段可回读，但不切换成 Kazumi 的平台实现或启用不可靠裁流算法。

广告自动跳过由客户端根据明确 CUE-OUT/CUE-IN 区间及实际时间轴决定，无明确广告证据时不猜测跳过正片。本仓库不存用户账号、Cookie、私钥或设备配置；上游声明的公开客户端标识随原规则保留。
