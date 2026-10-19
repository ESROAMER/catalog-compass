# Catalog Compass 投稿材料

代码、中英文文章和演示视频已公开在 [GitHub 仓库](https://github.com/ESROAMER/catalog-compass)。[英文参赛文章](https://dev.to/esroamer/catalog-compass-helps-freelancers-review-supplier-csvs-with-local-ai-1b6d)已于北京时间 **2026 年 10 月 19 日 13:11:44** 发布到 DEV。

- `article.en.md`：已发布英文文章的源稿，保留官方模板主要栏目及必需标签。
- `article.zh-CN.md`：与英文稿逐段对应的中文审阅稿，便于核对内容和提出修改意见。
- `index.html`：本地阅读预览，可同时播放视频。
- `video/catalog-compass-demo.mp4`：约 2 分 25 秒、1920×1080、24 fps，英文合成配音与内嵌字幕。
- `video/captions.en.srt`：独立字幕，便于视频平台使用。
- `video/narration.en.md`、`video/storyboard.json`：可修改的解说词和分镜。
- `video/captures/`：从真实应用获取的原始界面截图。
- `video/timeline.json`：时间线、截图 SHA256 和制作方式。
- `demo-supplier.csv`、`demo-issue-report.csv`：视频所用虚构样例及实际下载的检查报告。

视频是使用真实界面截图制作的讲解剪辑，并非连续操作录屏。实际运行了 Qwen3-0.6B，保留了模型将 `Kind` 同时分给 Product type 和 Description 的错误，以及人工修正。API 片段只展示接入设置，没有宣称实际调用了付费远程服务。画面中的模型耗时是该次运行的观察值，不是性能保证。

## 发布记录

1. DEV 作者账号：`esroamer`（HTZhao）。文章包含官方模板栏目，以及 `devchallenge`、`hf26challenge` 和 `opensource` 标签。
2. 文章提供公开仓库和 [YouTube 演示](https://youtu.be/7ixUD3DLN7Y)链接，保留 [MP4 文件](https://github.com/ESROAMER/catalog-compass/blob/master/submission/video/catalog-compass-demo.mp4)作为备用下载，并标注为 AI-assisted。
3. DEV 页面记录的发布时间为 `2026-10-19T05:11:44Z`，即北京时间 **13:11:44**，早于当天 **14:59** 的投稿截止时间。
4. YouTube Studio 已确认视频预定于北京时间 **2026 年 10 月 19 日 14:45** 公开（`2026-10-19T06:45:00Z`）；发布前视频为私享状态。视频时长 2:25，版权检查未发现问题。

材料没有声称已有付费客户、已获得独立准确率或时间节省数据，也没有申报未使用的合作伙伴奖项。AI 辅助开发及合成解说已披露。

## 重新生成

`video/make_narration.ps1` 使用 Windows 自带的 Microsoft Zira Desktop 语音，按分镜生成 WAV。需要修改解说时先编辑 `storyboard.json`。

`video/build_video.py` 使用 Pillow 和 imageio-ffmpeg 0.6.0 合成 MP4、字幕和时间线；它只处理已经保存的素材，不操作或录制桌面。中间文件位于忽略的 `video/build/`。演示成品可直接上传，无须运行这些工具。

`build_preview.mjs` 使用 marked 将英文文章转换为预览页面，可以将 marked 的模块目录作为第一个命令行参数传入。
