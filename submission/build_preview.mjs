import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const {marked} = await import(pathToFileURL(require.resolve(process.argv[2] || 'marked')));
const root = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(path.join(root, 'article.en.md'), 'utf8');
const body = source.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, '');
const article = marked.parse(body);
const html = `<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Catalog Compass 投稿材料预览</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f6f2;color:#173c33;font:18px/1.7 system-ui,-apple-system,"Segoe UI",sans-serif}header,main,footer{max-width:1120px;margin:auto;padding:28px}header{padding-top:46px}h1{font-size:34px;line-height:1.3;margin:8px 0 18px}h2{font-size:26px;margin:38px 0 14px;line-height:1.4}h3{font-size:21px;line-height:1.4}p{margin:14px 0}a{color:#176a53;text-underline-offset:3px}.tag{font-size:16px;background:#fff0cf;padding:6px 12px;border-radius:6px}.intro{max-width:800px}.actions{display:flex;flex-wrap:wrap;gap:12px;margin:20px 0}.actions a{padding:9px 15px;background:#173f34;color:#fff;border-radius:6px;text-decoration:none}.actions a.secondary{background:#e3ebe5;color:#173f34}video{width:100%;display:block;border-radius:12px;background:#102e2a}.meta{font-size:16px;color:#52675e}.article{max-width:820px;margin:50px auto;padding:28px 40px;background:#fff;border:1px solid #d8e1d8;border-radius:12px;color:#253c33}.article h2{padding-top:10px;border-top:1px solid #e4eae5}.article h2:first-of-type{border-top:0}.article p,.article li{line-height:1.75}.article code{background:#eff3ed;padding:2px 5px;border-radius:3px;font-size:.9em}.article pre{padding:16px;background:#eff3ed;overflow:auto}.article pre code{padding:0}#publishing{border-left:4px solid #c79c45;background:#fff8e7;padding:20px 24px}.article ul,.article ol{padding-left:26px}footer{font-size:16px;color:#52675e;padding-bottom:48px}@media(max-width:700px){header,main,footer{padding:20px}h1{font-size:28px}.article{padding:20px;margin:30px 0}h2{font-size:24px}}
</style></head><body>
<header><span class="tag">GitHub 材料已公开 · DEV 文章待发布</span><h1>Catalog Compass 投稿材料</h1><p class="intro">先看演示视频，再审阅英文文章。内容展示真实本地推理、一次列映射冲突、人工修正和检查报告。</p><nav class="actions"><a href="#video">观看视频</a><a class="secondary" href="#article">阅读英文文章</a><a class="secondary" href="#publishing">查看发布前剩余项</a></nav></header>
<main><section id="video"><h2>演示视频</h2><video controls preload="metadata" poster="video/poster.jpg" aria-label="Catalog Compass narrated demo"><source src="video/catalog-compass-demo.mp4" type="video/mp4"></video><p class="meta">2 分 25 秒 · 1080p · 英文合成配音与内嵌字幕 · 真实界面画面剪辑，并非连续操作录屏</p><div class="actions"><a href="video/catalog-compass-demo.mp4" download>下载 MP4</a><a class="secondary" href="video/captions.en.srt" download>英文字幕</a><a class="secondary" href="demo-supplier.csv" download>样例 CSV</a><a class="secondary" href="demo-issue-report.csv" download>样例检查报告</a></div></section>
<section id="article" class="article" lang="en"><p class="meta">DEV article draft · about 1,300 words</p><h1>Catalog Compass helps freelancers review supplier CSVs with local AI</h1>${article}</section>
<section id="publishing"><h2>下一步：发布 DEV 文章</h2><p>代码、视频和文章草稿已公开在 <a href="https://github.com/ESROAMER/catalog-compass">GitHub 仓库</a>。英文稿已填入仓库和 MP4 链接；GitHub 页面提供视频下载。如希望在 DEV 内直接播放，可以另外上传至支持嵌入的视频平台。</p><p>稿件已包含官方模板的主要栏目以及 <code>devchallenge</code>、<code>hf26challenge</code> 标签。在 DEV 发布文章才算提交。截止时间为北京时间 2026 年 10 月 19 日 14:59。</p><p><a href="article.en.md" download>下载英文投稿稿</a> · <a href="https://dev.to/challenges/hacktoberfest-week2-2026-10-12">官方比赛页面</a></p></section></main><footer>本地素材包仅包含虚构商品数据。视频未展示或使用任何真实 API 密钥。</footer></body></html>`;
fs.writeFileSync(path.join(root, 'index.html'), html);
console.log('Preview written: ' + path.join(root, 'index.html'));
