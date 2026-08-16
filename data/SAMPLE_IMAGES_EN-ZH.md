# Online Sample Images and Week 2 Results
# 在线样本图片与第二周测试结果

## Purpose / 目的

**English:** These images are used only to verify image download, JPEG decoding, resolution handling and the basic OpenCV edge/contour pipeline. They are not a labelled rPLA filament defect dataset.

**中文：** 这些图片仅用于验证图片下载、JPEG 解码、分辨率处理和基础 OpenCV 边缘/轮廓流程。它们不是带标注的 rPLA 线材缺陷数据集。

## Samples and Licensing / 样本与授权

| Local file / 本地文件 | Description / 说明 | Source and licence / 来源与授权 |
|---|---|---|
| `pla_white_filament.jpg` | Packaged white PLA filament; 1280 × 857.<br>包装中的白色 PLA 线材；1280 × 857。 | Gary C Martin, [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:PLA_White_filament.jpg), CC BY 2.0.<br>作者 Gary C Martin，Wikimedia Commons，CC BY 2.0。 |
| `plastic_surface_texture.jpg` | Repeating rough plastic texture; 1024 × 768.<br>重复的粗糙塑料纹理；1024 × 768。 | Titus Tscharntke, [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Plastic_surface_texture.jpg), public domain.<br>作者 Titus Tscharntke，Wikimedia Commons，公有领域。 |
| `scratched_dirty_plastic.jpg` | Dirty plastic surface with many scratches; 1344 × 896.<br>带有大量划痕的脏污塑料表面；1344 × 896。 | Drazen Nesic, [Pixnio](https://pixnio.com/media/plastic-white-dirty-texture-surface), Pixnio free-use licence.<br>作者 Drazen Nesic，Pixnio 免费使用许可。 |

## Test Results / 测试结果

| Input / 输入 | Significant contours / 显著轮廓数 | Pipeline status / 管线状态 |
|---|---:|---|
| `pla_white_filament.jpg` | 48 | PASS |
| `plastic_surface_texture.jpg` | 43 | PASS |
| `scratched_dirty_plastic.jpg` | 909 | PASS |

**English:** The contour counts are not defect counts. The current general-purpose Canny pipeline also responds to labels, packaging, repeated ribs, dirt and background texture.

**中文：** 轮廓数量不是缺陷数量。当前通用 Canny 流程也会响应标签、包装、重复条纹、污渍和背景纹理。

**English:** The next valid step is to capture a single filament under controlled lighting, crop a fixed region of interest and develop rules specific to the filament surface.

**中文：** 下一步应在受控光照下拍摄单根线材，裁剪固定感兴趣区域，并开发针对线材表面的专用规则。

## Re-run Commands / 重新运行命令

```powershell
.\.venv\Scripts\python.exe src\week2_opencv_check.py `
  --input data\input\scratched_dirty_plastic.jpg `
  --output data\output\scratched_dirty_plastic_annotated.jpg
```
