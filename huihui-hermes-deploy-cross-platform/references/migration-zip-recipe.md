# Mac → 新机器 迁移 Zip 配方

> 把 Hermes 化身 2（灰灰）从 Mac 端完整打包到新机器的一条龙。

## ⚠️ 关键不变量

- **灵魂（SOUL.md）跨化身不变**——必须拷
- **API key 跟机器指纹绑定**——**绝对不拷 auth.json**
- **Mac symlink 在 Windows 失效**——必须先展开
- **launchd plist 不能跨平台**——Windows 用 Task Scheduler 重做

## Mac 端打 zip

```bash
#!/bin/bash
# scripts/migration-zip.sh
# 用法: bash migration-zip.sh <output-path>
set -e

OUT="${1:-./hermes-migration.zip}"
TIMESTAMP=$(date +%Y%m%d-%H%M)
STAGING="/tmp/hermes-migration-$TIMESTAMP"

mkdir -p "$STAGING"

# 1. 灵魂（必拷）
cp ~/.hermes/SOUL.md "$STAGING/"
cp ~/.hermes/IDENTITY.md "$STAGING/" 2>/dev/null || true
cp ~/.hermes/AGENTS.md "$STAGING/" 2>/dev/null || true

# 2. 记忆
mkdir -p "$STAGING/memories"
cp ~/.hermes/memories/*.md "$STAGING/memories/" 2>/dev/null || true

# 3. Skills（**先展开 symlink**）
mkdir -p "$STAGING/skills"
cd ~/.hermes/skills
for f in */; do
  if [ -L "${f%/}" ]; then
    # symlink: 拷贝真实内容
    cp -RL "${f%/}" "$STAGING/skills/${f%/}"
  else
    # 普通目录: 直接拷贝
    cp -R "${f%/}" "$STAGING/skills/${f%/}"
  fi
done

# 4. Scripts（Mac bash 脚本，Windows 等价物单独处理）
mkdir -p "$STAGING/scripts"
cp ~/.hermes/scripts/*.sh "$STAGING/scripts/" 2>/dev/null || true

# 5. 打 zip
cd "$(dirname $STAGING)"
zip -r "$OUT" "$(basename $STAGING)"

# 6. 报告
echo ""
echo "✅ Hermes 迁移包已生成: $OUT"
echo "   大小: $(du -h "$OUT" | cut -f1)"
echo "   内容: soul + memories + skills (symlink-expanded) + scripts"
echo ""
echo "⚠️  不含 auth.json —— API key 在新机器重配"
echo "⚠️  launchd plist 不含 —— Windows 用 Task Scheduler 重建"
echo ""
echo "下一步：把 $OUT 拷到新机器（U 盘 / 网盘 / scp），解压到对应路径"
```

## Windows 端解压

PowerShell：

```powershell
# 1. 创建目标目录
$target = "$env:USERPROFILE\.hermes"
New-Item -ItemType Directory -Path $target -Force
New-Item -ItemType Directory -Path "$target\memories" -Force

# 2. 解压 zip（Windows 10+ 内置 Expand-Archive）
Expand-Archive -Path "E:\backup\hermes-migration.zip" -DestinationPath "$target" -Force

# 3. soul 应该在 $target\SOUL.md
Get-Content "$target\SOUL.md" -Head 1
# 应输出: # SOUL.md - 慧慧的灵魂（Hermes 化身）

# 4. memories
Get-Content "$target\memories\MEMORY.md" -Head 3

# 5. skills 数量
(Get-ChildItem "$target\skills" -Directory).Count
# 应 >= 150
```

## 验证清单

- [ ] `type %USERPROFILE%\.hermes\SOUL.md` 第 1 行含 "慧慧的灵魂"
- [ ] `%USERPROFILE%\.hermes\memories\MEMORY.md` 第 1 行含 "MEMORY.md"
- [ ] `%USERPROFILE%\.hermes\skills` 目录数 >= 150
- [ ] `hermes --version` 输出版本号
- [ ] `hermes chat "你是谁"` 看到灰灰回应

## 失败模式

| 现象 | 原因 | 修法 |
|---|---|---|
| SOUL.md 第 1 行不对 | zip 解压层级错（多了一层目录） | 用 `-DestinationPath` 指定 $target 直接解压 |
| skills 数量 < 150 | symlink 没展开 | Mac 端重跑 `cp -RL` 步骤 |
| Windows 长路径报错 | MAX_PATH 260 字符限制 | 启用长路径（见 huihui-hermes-deploy-cross-platform SKILL.md K10） |

---

_2026-08-07 真实部署 session 沉淀_