# Limbus-glyph-zero-pack

自维护字形替换表 + **零协**语言包 → 安卓游戏 `jp.zip` 的可复现打包流水线。

| 项 | 值 |
|----|-----|
| 上游文本信任根 | [LocalizeLimbusCompany（零协）](https://github.com/LocalizeLimbusCompany/LocalizeLimbusCompany) |
| 替换行为参照 | 社区安卓/iOS 汉化实践（[ghcruise/LimbusCompany-IOS-Localization](https://github.com/ghcruise/LimbusCompany-IOS-Localization)、[pzwboy/LocalizeLimbusCompanyForAndroid](https://github.com/pzwboy/LocalizeLimbusCompanyForAndroid)）—— 2026-09-21 提取并重建 |
| 输出路径 | `Android/data/com.ProjectMoon.LimbusCompany/files/Assets/Resources_moved/Localize/jp/**` |
| 维护 | [@kermond369-nsis](https://github.com/kermond369-nsis) |
| 仓库 | 私有（`Limbus-glyph-zero-pack`） |

**原则**：文本以零协为准；替换行为与社区实证方案等效；显示安全由本仓库 `glyph_map` + `safe_charset` 闭环校验保证。

## 架构（v2, 2026-09-21）

```text
零协 LimbusLocalize_*.7z/.zip
        │
        ▼
scripts/pack_zero_to_jp.py
   ├─ 解压 → 找 LLC_zh-CN 目录
   ├─ 词组规则（长键优先）→ 单字替换（str.translate）
   ├─ 闭环校验：产物非 ASCII 字符必须 ⊆ assets/safe_charset.txt（Hangul 豁免）
   ├─ 输出 jp.zip（+ jp.zip.sha256）+ jp.zip.report.json（替换统计）
   └─ 任何闭环失败 = fail-fast
        ▼
jp.zip  →（写入方式见此前的"Android_data 写入方案"文档）
```

## 本地用法

```bash
# 依赖: python3 + 7z
python3 scripts/pack_zero_to_jp.py \
  --input /path/to/LimbusLocalize_or_extracted \
  --output jp.zip \
  --glyph-map assets/glyph_map.json \
  --safe-charset assets/safe_charset.txt

# 表审计（lint + 语料 dry-run）
python3 scripts/audit_glyph_map.py --corpus /path/to/LimbusLocalize.zip
```

产物：`jp.zip` + `jp.zip.sha256` + `jp.zip.report.json`。

## 资产说明

| 文件 | 含义 |
|------|------|
| `assets/glyph_map.json` | `源 → 替换串`：1418 条单字 + 8 条词组规则；单字基于社区方案提取重建（同日文字形为主），词组规则含特殊改写（`啥→什么`、`螃蟹→蟹`、`Девять→九` 等） |
| `assets/safe_charset.txt` | 闭合校验集：参照方案成品中出现过的全部字符（4612 个）——产物字符必须全部落在其中（Hangul 豁免，理由：游戏为韩语原生，字体链必然覆盖） |
| `assets/font_ok.txt` | （legacy）旧版 CJK 白名单；App 侧兼容保留，打包脚本不再依赖 |

## 字形表维护

- 新增/修改映射：改 `assets/glyph_map.json`（单字长度 1 / 词组长度 >1）。
- 提交前必跑：`python3 scripts/audit_glyph_map.py --corpus <语料>`（0 error 才可提交）。
- 零协更新后：重跑打包；若 CI/本地报"outside safe charset"，说明出现新字符，
  按三选一处理：① 找到等价可显示字形加入表；② 词组改写；③ 确认真实可显示后把字符补入 `safe_charset.txt`（需附证据）。

## CI 用法

1. Actions → **Build jp.zip** → Run workflow
2. `source_url` 留空 = 自动取零协 latest Release 资产
3. 需要时勾选 `publish_release` 并填 `tag_name`
4. 下载 Artifact：`jp.zip` + `.sha256` + `.report.json`

## 许可

- **代码与"字符 → 字形"映射表**：MIT（见 [LICENSE](./LICENSE)）
- **零协译文正文**：CC BY-NC-SA 4.0 —— 本仓**不**托管游戏本地化全文；你须自行获取
- 替换行为参照社区开源汉化项目（致谢同上）

## 免责

非官方工具，仅用于个人客户端资源替换实验。请遵守游戏用户协议与社区规范，勿商业分发译文。
