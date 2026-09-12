# Limbus-glyph-zero-pack

自维护字形映射 + **零协**语言包 → 安卓游戏 `jp.zip` 的可复现打包流水线。

| 项 | 值 |
|----|-----|
| 上游信任根 | [LocalizeLimbusCompany（零协）](https://github.com/LocalizeLimbusCompany/LocalizeLimbusCompany) |
| 输出路径 | `Android/data/com.ProjectMoon.LimbusCompany/files/Assets/Resources_moved/Localize/jp/**` |
| 维护 | [@kermond369-nsis](https://github.com/kermond369-nsis) |
| 仓库 | 私有（`Limbus-glyph-zero-pack`） |

**原则**：不信任第三方二次打包；中文文本仍以零协为准；字形安全由本仓库 `glyph_map` + CI 闭环保证。

## 架构

```text
零协 LimbusLocalize_*.7z   ──►  scripts/pack_zero_to_jp.py  ──►  jp.zip
        ▲                               │
        │ 你自备 HTTPS 源               ├─ assets/font_ok.txt   （游戏已可显示 CJK）
        │                               └─ assets/glyph_map.json（缺字必替换，可多字）
        ▼
 GitHub Actions（.github/workflows/build-jp.yml）
   workflow_dispatch → 下载 source_url → pack → Artifact / 可选 Release
```

### 为何不在 CI 里自动爬零协？

官网下载带验证码；网络与体积不可控。本仓只做**确定性转换**，输入由你提供。

## 本地用法

```bash
# 依赖: python3 + 7z
python3 scripts/pack_zero_to_jp.py \
  --input /path/to/LimbusLocalize_or_extracted \
  --output jp.zip \
  --glyph-map assets/glyph_map.json \
  --font-ok assets/font_ok.txt
```

产物旁会生成 `jp.zip.sha256`。

## CI 用法

1. Actions → **Build jp.zip** → Run workflow  
2. 填 `source_url`（你托管的 `.7z`/`.zip` HTTPS 直链）  
3. 需要时勾选 `publish_release` 并填 `tag_name`  
4. 下载 Artifact：`jp.zip` + `jp.zip.sha256`

## 字形表维护

| 文件 | 含义 |
|------|------|
| `assets/font_ok.txt` | 日文语言包槽位里已出现、可稳定显示的 CJK |
| `assets/glyph_map.json` | `源字 → 替换串`；可多字（如 `"啥": "什么"`） |

游戏再缺字时：加一条 map 即可，CI/本地/App 同一表。

## 许可

- **代码与字形表**：MIT（见 [LICENSE](./LICENSE)）  
- **零协译文正文**：CC BY-NC-SA 4.0 —— 本仓**不**托管游戏本地化全文；你须自行获取  

致谢：LocalizeLimbusCompany / 都市零协会。

## 免责

非官方工具，仅用于个人客户端资源替换实验。请遵守游戏用户协议与社区规范，勿商业分发译文。
