# Third-Party Notices & Licensing Boundaries

本文档明确说明本仓库源码/映射表与编译产物之间的开源协议边界、上游归属及修改声明。

---

## 1. 双层许可边界（Dual-Layer Licensing）

| 范围 | 内容 | 适用协议 |
|---|---|---|
| **仓库本体源码与字形工具资产** | `scripts/`、`assets/`（`glyph_map.json`、`safe_charset.txt` 等纯字符映射与集合）、`.github/workflows/`、`docs/` | [**MIT License**](./LICENSE) |
| **GitHub Releases 打包产物** | `jp.zip`（含经过字形替换与目录重组后的游戏本地化 JSON 文本） | [**CC BY-NC-SA 4.0**](https://creativecommons.org/licenses/by-nc-sa/4.0/) |

- 本仓库 Git 历史与工作树中**不托管、不分发**《边狱巴士》或上游汉化组的任何本地化文本正文。
- 任何经由本流水线构建并发布的 `jp.zip` 均属于上游本地化文本的衍生作品，必须严格遵守 **署名-非商业性使用-相同方式共享 4.0 国际（CC BY-NC-SA 4.0）** 协议：**禁止任何形式的商业用途**，二次分发须保留上游署名并沿用相同协议。

---

## 2. 上游与参照项目归属（Upstream & Reference Attribution）

### 上游中文译文来源（Upstream Localization）
- **项目名称**：LocalizeLimbusCompany / 都市零协会汉化组
- **GitHub 仓库**：[LocalizeLimbusCompany/LocalizeLimbusCompany](https://github.com/LocalizeLimbusCompany/LocalizeLimbusCompany)
- **官方网站**：<https://www.zeroasso.top>
- **适用协议**：[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
- **修改说明（Modification Disclosure）**：
  - 本流水线对上游 `LLC_zh-CN` 文本包仅执行自动化字符/词组替换（将游戏日文槽位字体链不支持的简体中文字符映射为可显示的日语/CJK 字形，并清理不可显示的零宽控制字符如 `U+200C`），以及将目录结构重打包为安卓客户端路径 `Android/data/com.ProjectMoon.LimbusCompany/files/Assets/Resources_moved/Localize/jp/`（文件前缀统一为 `JP_`）。
  - 除极少数为兼容显示而引入的短词组替换规则外，未改动上游译文的翻译含义与剧情内容。

### 字形替换行为参照（Glyph Replacement References）
本仓库 `assets/glyph_map.json` 与 `assets/safe_charset.txt` 的字符替换策略参照以下社区开源本地化项目提取并闭环验证：
1. **[ghcruise/LimbusCompany-IOS-Localization](https://github.com/ghcruise/LimbusCompany-IOS-Localization)**（CC BY-NC-SA 4.0）
2. **[pzwboy/LocalizeLimbusCompanyForAndroid](https://github.com/pzwboy/LocalizeLimbusCompanyForAndroid)**（CC BY-NC-SA 4.0）

---

## 3. 原作版权声明（Game Copyright）

- **原作游戏**：*Limbus Company*（《边狱巴士》）© Project Moon.
- 本项目为非官方社区辅助工具，与 Project Moon 无任何从属、合作或官方授权关系。所有游戏资产、商标与版权归 Project Moon 所有。
