---
name: pyinstaller-release-decompile
description: Use when 要从 PyInstaller 发布包提取/反编译源码，或旧提取方法对新版包失效。
---

# PyInstaller 发布包反编译流水线

适用：PyInstaller onefile ELF（Linux/macOS）或 .exe，需要恢复业务源码。全程不需要运行目标程序——纯字节解析，静态安全。

## 判断提取难度（第一步就做）

1. `strings -n 8 <bin> | grep -E 'MEIPASS|pyi-|python 3\.'` 确认 PyInstaller + Python 版本。
2. 自写解析器读尾部 cookie（魔数 `MEI\x0c\x0b\x0a\x0b\x0e`，rfind 最后一个）。
3. **先试小端再试大端**：按 cookie 中 toc_off+toc_len 恰好落在 cookie 位置做 sanity check，不合理就换端序。标准 PyInstaller 是小端；厂商改大端 = 防提取改造（pyinstxtractor 等现成工具直接报废，必须自写解析器）。
4. cookie 后面可能还有 ~2KB section 字符串表——**cookie 不在 EOF** 是正常的，别因此否定定位。

## CArchive 结构

- cookie：magic(8) + len_pkg/toc_off/toc_len/pyvers(u32×4) + pylibname(64)。archive_base = cookie_pos + cookie_size − len_pkg。
- TOC entry：`elen(u32) | dpos,ulen,flen(u32×3) | flag(u8) | type(char) | name`（entry 头端序同 TOC）。
- type：`s/m`=bootloader 模块（**只有十来个，不是业务代码**）、`b`=二进制 so、`x`=数据文件、`z`=PYZ 归档（业务代码全在这）。

## 版本指纹

TOC 里找构建信息文件（常见名 `*-build-info.json`，type x），解出来直接得 version/revision/built_at。先拿它确认版本再继续，别对着未知版本啃。

## PYZ 提取（核心）

- 头部：`PYZ\x00` + pyc magic 4B + toc_off(u32 大端)；flag=0 时整段不压缩，直接切片。
- 尾部 TOC 是 **marshal 序列化的 list**，不是 zlib——`zlib.decompress` 报 `incorrect header check` 就是在拿 zlib 解 marshal，换 `marshal.loads`。
- 用本机任意 CPython 读 marshal TOC 即可（marshal 只含名字和偏移，跟目标字节码版本无关，3.14 能读 3.12 的）。entry = `(name, (ispkg, pos, ulen))`。
- 每项 `zlib.decompress(pyz[pos:pos+ulen])` 得到**无头 pyc**（PyInstaller 剥掉了 16B 头）。

## 补头 + 反编译

```bash
# pycdc 不在机器上时（新环境每次都要装）
cd /tmp && git clone --depth 1 https://github.com/zrax/pycdc && cd pycdc && cmake . && make -j4

# 补 pyc 头：magic(4B, 按目标 Py 版本) + 12 零字节，前插
python3 - <<'EOF'
import os
MAGIC = bytes([0xcb,0x0d,0x0d,0x0a])  # Py3.12; 其它版本查 importlib.util.MAGIC_NUMBER
for root,_,files in os.walk('pyz-out'):
    for fn in files:
        p = os.path.join(root,fn)
        d = open(p,'rb').read()
        if d[:4] != MAGIC: open(p,'wb').write(MAGIC+b'\0'*12+d)
EOF

# 批量反编译
for f in $(find pyz-out -name '*.pyc'); do
  rel=${f#pyz-out/}; out=new-src/${rel%.pyc}.py; mkdir -p $(dirname $out)
  /tmp/pycdc/pycdc "$f" > "$out" 2>/dev/null || echo "FAIL: $f"
done
```

- pycdc 对 lambda/推导式会出 `# WARNING: Decompyle incomplete`——语义基本完整可继续用；整模块失败时用 `pycdas <file>.pyc > <file>.asm` 反汇编提取常量（步骤名/路径/正则），别硬啃。
- 质量校验：`grep -rc 'WARNING' new-src | sort -t: -k2 -rn | head`，抽查首屏 import 和常量是否合理。

## 固化为知识（收尾必做）

1. 源码归档到知识库（如 `~/.hermes/knowledge/wiki/<tool>/decompiled-src-<version>/`），失败模块 asm 同目录 `<module>-<version>.asm`。
2. 归档目录 README 写：基准版本/revision/md5、端序、模块清单、历史版本说明。
3. 对应工具技能更新基准行并补新模块章节——过时描述就地改写，不追加 UPDATE。
4. 临时目录用完即清：>200MB 的 tar.gz 和解出二进制别留在 tmp。

## 坑

- **别对防提取包用 pyinstxtractor**：端序被改过就 extracted 0 + 一堆 insane 值，直接自写解析器。
- **文件里可能有多处伪 MEI 魔数**：rfind 最后一个 + 字段合理性双重校验，别见 magic 就信。
- **大包分步走**：>200MB 时提取/解压一步一查（find 计数），单条命令超时会丢进度。
- **新 Py 版本的 magic 要查表**：`python3 -c "import importlib.util; print(importlib.util.MAGIC_NUMBER.hex())"` 用目标版本解释器跑，别猜。

## 实例参照

autolife-robot-manager v0.2.0（大端改造包）：归档在 `~/.hermes/knowledge/wiki/autolife-robot-manager/`，提取脚本 `extract_pkg.py` 同目录，52 模块 51 个完整还原，configuration_workflow/ssh_client 两模块 pycdc 失败由 pycdas asm 补全。技能细节见 `autolife-robot-manager-toolbox`（用户所有，未纳入 curator 管理）。
