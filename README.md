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
