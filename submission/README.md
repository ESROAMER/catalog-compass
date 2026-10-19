# Catalog Compass 投稿材料

本目录为可审阅的投稿素材，尚未发布到 DEV、视频平台或公开代码仓库。

- `article.en.md`：约 1,300 词的英文文章，保留官方模板主要栏目及必需标签。
- `index.html`：本地阅读预览，可同时播放视频。
- `video/catalog-compass-demo.mp4`：约 2 分 25 秒、1920×1080、24 fps，英文合成配音与内嵌字幕。
- `video/captions.en.srt`：独立字幕，便于视频平台使用。
- `video/narration.en.md`、`video/storyboard.json`：可修改的解说词和分镜。
- `video/captures/`：从真实应用获取的原始界面截图。
- `video/timeline.json`：时间线、截图 SHA256 和制作方式。
- `demo-supplier.csv`、`demo-issue-report.csv`：视频所用虚构样例及实际下载的检查报告。

视频是使用真实界面截图制作的讲解剪辑，并非连续操作录屏。实际运行了 Qwen3-0.6B，保留了模型将 `Kind` 同时分给 Product type 和 Description 的错误，以及人工修正。API 片段只展示接入设置，没有宣称实际调用了付费远程服务。画面中的模型耗时是该次运行的观察值，不是性能保证。

## 投稿前完成

1. 将项目发布到公开代码仓库，并将文章中的 `{{REPOSITORY_URL}}` 替换为仓库地址。
2. 将 MP4 上传到能公开访问的视频地址，替换 `{{DEMO_URL}}`。必要时换成 DEV 支持的视频嵌入格式。
3. 使用 [本期投稿模板](https://dev.to/challenges/hacktoberfest-week2-2026-10-12) 发布英文文章，保留 `devchallenge` 和 `hf26challenge` 标签。
4. 检查未登录的访客能够访问代码、视频和文章。北京时间截止时间为 **2026 年 10 月 19 日 14:59**。

材料没有声称已有付费客户、已获得独立准确率或时间节省数据，也没有申报未使用的合作伙伴奖项。AI 辅助开发及合成解说已披露。

## 重新生成

`video/make_narration.ps1` 使用 Windows 自带的 Microsoft Zira Desktop 语音，按分镜生成 WAV。需要修改解说时先编辑 `storyboard.json`。

`video/build_video.py` 使用 Pillow 和 imageio-ffmpeg 0.6.0 合成 MP4、字幕和时间线；它只处理已经保存的素材，不操作或录制桌面。中间文件位于忽略的 `video/build/`。演示成品可直接上传，无须运行这些工具。

`build_preview.mjs` 使用 marked 将英文文章转换为预览页面，可以将 marked 的模块目录作为第一个命令行参数传入。
