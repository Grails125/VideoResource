# VideoResource

短剧汇在线源仓库。当前版本 **0.0.124+203** 已移除 Kazumi 搜索和播放器备用线路，青空恢复原生目录、搜索、详情及默认播放接口。

所有版本只内置红果、B站和看剧AI，其余已支持的十个来源通过配置安装。稳定键直接使用 `hanxiaoquan`、`sorani` 等名称，无需 `native:` 前缀；旧前缀仍兼容原来源身份。

在应用「设置 → 站源管理 → 添加 → 配置订阅」选择「VideoResource 源仓库」，或填写以下地址，获取后检查预览再确认。保留来源ID、个人顺序、隐藏、权限及观看和下载资料，不自动解锁来源。

| 配置 | 内容 |
| --- | --- |
| [config.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/config.json) | 十个可选原生来源 |
| [native.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/native.json) | 与默认配置相同，保留原订阅地址 |
| [kazumi.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/kazumi.json) | 旧订阅兼容入口，仅青空默认配置，无备用线路 |
| [all.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/all.json) | 旧订阅兼容入口，仅青空默认配置，无备用线路 |
| [archive.json](https://raw.githubusercontent.com/Grails125/VideoResource/main/archive.json) | 旧订阅兼容入口，仅青空默认配置，无备用线路 |

十个可选来源为韩小圈、鬼片、青空、黄豆、剧果、野果、帝果、黄果视频、黄果AI、黄果旧版。仍需客户端对应的适配器，不承诺任意网站自动接入。

青空不再调用 Kazumi 站点或自动匹配同名作品。203 客户端兼容读取旧嵌套线路和独立规则配置，校验后让它们退出活动配置；启动不额外写入，正常保存时清理。原始规则JSON、数组和 `kazumi://` 分享链接已停止导入。旧线路观看记录保留，打开时提示重新选择剧集，不自动映射到其他作品。旧客户端先更新订阅可移除未自定义的线路，完整退出以203客户端为准。

`kazumi/` 内86份JSON仅作历史归档，文件字节、SHA-256和上游废弃标记保留，**不再作为可接入规则**。`index.json` 活动规则数为0，仅提供归档元数据。原规则来自 [Predidit/KazumiRules固定提交](https://github.com/Predidit/KazumiRules/tree/2fa4d28659f94e1eb52e7a38d79b7b9a5dcd605b)，遵循 [MIT许可](LICENSE.kazumi.txt)。

本次用合成API及本地配置验证恢复和迁移，未请求站源图片或视频；不代表真实站点当前可播放，网站及设备行为仍需实测。广告自动跳过只采用明确标记和可靠时间轴。本仓库不存账号、Cookie、私钥或设备配置。
