"""setup.py for cli-anything-ljg-ppt-design (HKUDS CLI-Anything hub 兼容包)。

不是替代 ljg-ppt-design,而是它的"hub entry"。装这个包后:

  - 拿到 `cli-anything-ljg-ppt-design` CLI 命令
  - 能在 HKUDS cli-hub 的 registry.json 里被注册
  - 跨 agent 平台 (Pi / OpenClaw / Claude Code) 都能用

依赖: 已经装了 ljg-ppt-design (本目录的兄弟模块)
"""

from setuptools import setup, find_packages

with open("README_HUB.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-ljg-ppt-design",
    version="0.1.0",
    description="HKUDS CLI-Anything hub entry for ljg-ppt-design — 4 preset × 12 layout × 4 talk type × 5-dim review + python-pptx/LibreOffice backends",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="ljg-ppt-design contributors",
    url="https://github.com/HKUDS/CLI-Anything",
    project_urls={
        "Upstream": "https://github.com/HKUDS/CLI-Anything",
        "ljg-ppt-design Source": "~/.claude/skills/ljg-ppt-design/",
    },
    python_requires=">=3.9",
    install_requires=[
        "click>=8.0",
        # ljg-ppt-design skill itself must be importable; user installs separately
        # or symlink: ~/.claude/skills/ljg-ppt-design/ in PYTHONPATH
    ],
    extras_require={
        "pptx": ["python-pptx>=1.0.0"],
        # libreoffice 后端:HKUDS 原版不通过 PyPI 分发,需手动装
        # pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=libreoffice/agent-harness
        # 然后 brew install --cask libreoffice
        "dev": ["pytest>=7.0"],
    },
    packages=find_packages(include=["cli_anything_ljg_ppt_design", "cli_anything_ljg_ppt_design.*"]),
    entry_points={
        "console_scripts": [
            "cli-anything-ljg-ppt-design=cli_anything_ljg_ppt_design.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Office Suites",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
