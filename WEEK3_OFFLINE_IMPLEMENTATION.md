# Week 3 软件架构与离线验证

## 已完成（不依赖实物）

本周实现了可替换相机来源的数据链：

```text
SyntheticCameraSource
        -> FramePacket
        -> BaselineVisionProcessor
        -> DetectionRecord
        -> SQLite + JSON + CSV + annotated frames
```

- `FramePacket` 固定图像、帧号、采集/接收时间、相机来源和连接状态。
- `DetectionRecord` 固定候选类型、像素框、面积、算法分数、分级和批次信息。
- `CameraSource` 是统一接口；之后可增加 `Esp32MjpegSource`（方案 B）和
  `Picamera2Source`（方案 A），而无需修改视觉或存储层。
- SQLite 已冻结 `batches`、`detections`、`system_events` 和 `calibrations` 四张表。
- 合成相机生成可重复的凹坑、划痕和污染候选图案，用于验证数据流，不用于证明
  rPLA 缺陷识别准确率。
- 离线输出明确标记为 `OFFLINE_SYNTHETIC_ONLY` / `synthetic_baseline`。

## 关键真实性限制

当前没有标定尺和编码器，因此 `position_mm` 与 `size_mm` 必须为 `null`。
数据模型会拒绝写入没有 `calibration_id` 的物理测量值。算法产生的是
`*_candidate`，不是经过真实样本验证的缺陷分类。

## 运行

在项目根目录使用已经建立的虚拟环境：

```powershell
.\.venv\Scripts\python.exe -m src.week3_offline_demo
```

默认结果写入 `data/output/week3_offline/`，包括 SQLite 数据库、JSON、CSV、
标注帧和 `summary.json`。配置位于 `config/week3_offline.json`。

## 拿到硬件后补测

- 方案 B：XIAO ESP32S3 Sense + OV3660 的 MJPEG 实际地址、帧率、延迟、断线恢复和温升。
- 方案 A：Raspberry Pi 4 + 全局快门相机的 Picamera2 适配器及曝光/触发验证。
- STM32 串口、编码器时间同步、实际位置与相机到执行器偏移。
- 受控照明、焦点、视野和 pixels-per-mm 标定。
- 真实 rPLA 样本、人工真值、独立测试集、准确率/召回率和不确定度。

方案 A 与方案 B 必须使用不同的标定记录和性能证据，不得混用。
