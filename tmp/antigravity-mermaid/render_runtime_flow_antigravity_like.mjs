import { writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const htmlPath = path.join(__dirname, "runtime-flow-antigravity-like.html");
const source = String.raw`flowchart LR
    subgraph MAIN["主路径"]
        direction TB
        S1["1. 检查关键不确定性、冲突、缺口<br/>若已污染推进，先显性化"]
        S2["2. 检查依据是否足够<br/>依据不足则回退或补充依据"]
        S3["3. 完成对象归类<br/>先分清对象类型，再进入后续判断"]
        S4["4. 区分已成立边界 / 仍待选择<br/>约束（constraint）路径 / 待决策候选（decision candidate）路径"]
        S5["5. 判断稳定等级<br/>已确认 / 高置信未确认 / 未决"]
        S6["6. 冲突检测后再进入正式事实层<br/>或结构化交接包（handoff package）"]
        S1 --> S2 --> S3 --> S4 --> S5 --> S6
    end

    subgraph EX["异常切出点"]
        direction TB
        E1["冲突分支<br/>入口：第 1 步 / 第 6 步"]
        E2["依据不足<br/>入口：第 2 步"]
        E3["待复核分支<br/>入口：第 5 步"]
        E4["替代分支<br/>入口：待复核后"]
        E5["越级分支<br/>入口：第 2 步"]
        E6["交接降格分支<br/>入口：第 6 步"]
        E3 -->|"复核后确认替代"| E4
    end

    S1 -->|"冲突"| E1
    S6 -->|"冲突"| E1
    S2 -->|"依据不足"| E2
    S2 -->|"不允许越级直升"| E5
    S5 -->|"稳定对象被动摇"| E3
    S6 -->|"进入交接会误导下游"| E6`;
const escaped = source
  .replace(/&/g, "&amp;")
  .replace(/</g, "&lt;")
  .replace(/>/g, "&gt;");

const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Antigravity-like Mermaid Render</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #ffffff;
      --panel: #ffffff;
      --text: #1f2937;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 24px;
    }
    .wrap {
      width: 100%;
      max-width: 800px;
      margin: 0 auto;
    }
    .mermaid-host {
      width: 100%;
      overflow-x: auto;
      overflow-y: visible;
      background: var(--panel);
    }
    #graph {
      min-height: 400px;
    }
    pre {
      white-space: pre-wrap;
      display: none;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="mermaid-host">
      <div id="graph"></div>
    </div>
    <pre id="src">${escaped}</pre>
  </div>
  <script type="module">
    import mermaid from './node_modules/mermaid/dist/mermaid.esm.mjs';

    mermaid.initialize({
      startOnLoad: true,
      theme: 'default',
      securityLevel: 'loose',
      flowchart: {
        useMaxWidth: true,
        htmlLabels: true,
        curve: 'basis'
      },
      themeVariables: {
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
        fontSize: '14px'
      }
    });

    const source = document.getElementById('src').textContent;
    const { svg } = await mermaid.render('graph-svg', source);
    document.getElementById('graph').innerHTML = svg;
    document.body.setAttribute('data-rendered', 'true');
  </script>
</body>
</html>`;

await writeFile(htmlPath, html, "utf8");
console.log(htmlPath);
