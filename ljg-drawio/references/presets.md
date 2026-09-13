# ljg-drawio 参考手册

## 15 种 shape 全表

| key | drawio style | 推荐用途 |
|---|---|---|
| `rectangle` | `rounded=0;...` | 通用方框,UI 元素 |
| `rounded` | `rounded=1;...` | 服务/模块 |
| `ellipse` | `ellipse;...` | 状态/起点终点 |
| `diamond` | `rhombus;...` | 决策点 |
| `triangle` | `triangle;...` | 警告/提示 |
| `hexagon` | `shape=hexagon;...` | 准备/调整 |
| `cylinder` | `shape=cylinder3;...` | 数据库/存储 |
| `cloud` | `shape=cloud;...` | 外部服务/Internet |
| `parallelogram` | `shape=parallelogram;...` | 输入/输出 |
| `process` | `shape=process;...` | 预定义流程 |
| `document` | `shape=document;...` | 文件/报告 |
| `callout` | `shape=callout;...` | 注释/批注 |
| `note` | `shape=note;...` | 备注/便签 |
| `actor` | `shape=umlActor;...` | UML 角色 |
| `text` | `text;...` | 纯文本标签 |

## 6 种 edge style

| key | 视觉 | 推荐 |
|---|---|---|
| `straight` | 直线 | 简单连接 |
| `orthogonal` | 折线 (默认) | 流程图 |
| `curved` | 曲线 | 自由布局 |
| `entity-relation` | ER 风格 | 数据库 ER |
| `arrow` | 折线 + 箭头 | 数据流 (推荐) |
| `dashed-arrow` | 虚线箭头 | 弱依赖/可选 |

## 7 类 shape 分组

| category | 包含 |
|---|---|
| flow | rectangle, rounded, process, diamond, ellipse |
| data | cylinder, document, note |
| control | diamond, callout |
| ui | rectangle, rounded, text |
| cloud | cloud, rectangle |
| actor | actor |
| architecture | rectangle, cylinder, cloud, actor |

## 画布尺寸

默认 850×1100 (drawio 默认)。`Diagram(name, page_width, page_height, grid_size)` 可调。

## XML schema

```
<mxfile host="ljg-drawio" agent="ljg-drawio/0.1.0" version="24.0.0">
  <diagram id="..." name="Page-1">
    <mxGraphModel ... pageWidth="850" pageHeight="1100" ...>
      <root>
        <mxCell id="0"/>                                ← root container
        <mxCell id="1" parent="0"/>                     ← default layer
        <mxCell id="shape-XXX" value="Label"            ← shape
                style="rounded=1;..." vertex="1" parent="1">
          <mxGeometry x="100" y="100" width="120" height="60" as="geometry"/>
        </mxCell>
        <mxCell id="edge-YYY" value="reads"              ← edge
                style="...endArrow=classic;" edge="1" parent="1"
                source="shape-XXX" target="shape-ZZZ">
          <mxGeometry relative="1" as="geometry"/>
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

## 跟其他 skill 整合

- `ljg-ppt-design` 的 `content_image` 页 → `image_label` 可以是 drawio 出的图
- `ljg-drawio → ljg-ppt-design`:先 `diag.write("x.drawio")` → 用 LO 转 png → 当 ljg-ppt-design 的 `image_label` URL/path
- 跨 skill API 见 `ljg-ppt-design/integrations.md` (待写)
