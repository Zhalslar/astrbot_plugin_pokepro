
<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_pokepro?name=astrbot_plugin_pokepro&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# astrbot_plugin_pokepro

_✨ 专业戳一戳 ✨_  

[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0.html)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-4.0%2B-orange.svg)](https://github.com/Soulter/AstrBot)
[![GitHub](https://img.shields.io/badge/作者-Zhalslar-blue)](https://github.com/Zhalslar)
</div>

> 注意：戳一戳插件最新版依赖 `AstrBot v4.13.0+`  , 请先升级 AstrBot 至 v4.13.0+, 否则会无法加载插件

## 🤝 介绍

这是一个专业的戳一戳插件，机器人被戳时，会随机触发这些回复动作（跟戳、反戳、LLM回复、QQ表情、表情包、禁言、触发命令），也支持命令调用、关键词触发、定时戳。所有触发概率、回复内容均可自定义，开箱即用！

## 📦 安装

在 AstrBot 插件市场搜索 `astrbot_plugin_pokepro`，点击安装即可。

## ⚙️ 配置说明

### 基础设置

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `on_poke` | 开关 | 被戳监听总开关，开启后监听所有戳一戳事件 | `true` |
| `poke_cd` | 整数 | 用户戳 Bot 的冷却时间（秒），防连戳 | `10` |
| `follow_prob` | 小数 | 检测到别人被戳时，跟着戳一下的概率 | `0.1` |

### 回复动作配置（按权重随机触发）

所有回复动作都有 `weight`（触发权重），概率 = 本权重 / 所有权重之和。

#### 1. 反戳 (antipoke)

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `weight` | 整数 | 触发权重 | `10` |
| `max_times` | 整数 | 最大反戳次数（随机 1~N 次） | `5` |

#### 2. LLM 回复 (llm)

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `weight` | 整数 | 触发权重 | `10` |
| `template` | 文本 | LLM 提示模板，可用 `{username}` 变量 | `" {username} 戳了你一下..."` |

#### 3. QQ 表情回复 (face)

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `weight` | 整数 | 触发权重 | `10` |
| `pool` | 列表 | 表情 ID 池，随机选用 | `[1, 11, 14...]` |
| `max_copy_count` | 整数 | 最大复制数（随机发 1~N 个相同表情） | `3` |

#### 4. 表情包回复 (meme)

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `weight` | 整数 | 触发权重 | `10` |
| `pool` | 文件 | 本地表情包图片池 | `[]` |

#### 5. 禁言 (ban)

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `weight` | 整数 | 触发权重 | `10` |
| `duration` | 整数 | 基础禁言时间（秒） | `60` |
| `delta` | 整数 | 禁言时间波动范围（±秒） | `30` |
| `ban_template` | 文本 | 禁言成功时的 LLM 提示模板 | - |
| `ban_fail_template` | 文本 | 禁言失败时的 LLM 提示模板 | - |

#### 6. 触发命令 (command)

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `weight` | 整数 | 触发权重 | `10` |
| `pool` | 列表 | 命令池，随机触发一个（如"拍"、"吃"、"滚"等） | 见配置 |

### 主动戳设置

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `poke_max_times` | 整数 | 命令"戳 @某人 次数"的最大次数限制（管理员不受限） | `5` |
| `poke_interval` | 小数 | 发戳间隔（秒），防风控 | `0.5` |
| `poke_keywords` | 列表 | 消息含这些关键词时自动戳几下 | `[笨蛋, 人机, 机器人, bot]` |

### 定时戳 (scheduler)

| 配置项 | 类型 | 说明 | 默认值 |
|:------:|:----:|:-----|:------:|
| `enabled` | 开关 | 是否启用定时戳 | `true` |
| `cron` | 文本 | Cron 表达式（分 时 日 月 周） | `"30 22 * * *"` |
| `target` | 列表 | 发戳目标，格式 `群号:QQ号` | `["460973561:1959676873"]` |
| `times` | 整数 | 每次戳几下 | `1` |

## ⌨️ 命令表

| 命令 | 说明 |
|:----:|:-----|
| （被戳） | 被动触发：随机执行反戳/LLM/表情/表情包/禁言/命令 |
| `戳 @XXX` | 戳指定人，可跟数字指定次数（如`戳 3@张三`） |
| `戳我` | 戳你自己 |
| `戳全体成员` | 戳全员（200人以上群随机抽200人） |

## 👥 贡献指南

- 🌟 **Star 这个项目！**（点右上角的星星，感谢支持！）
- 🐛 提交 Issue 报告问题
- 💡 提出新功能建议
- 🔧 提交 Pull Request 改进代码

## 📌 注意事项

- 想第一时间得到反馈可以来作者的插件反馈群（QQ群）：**460973561**（不点 star 不给进）
