# Week 2 Development Environment
# 第二周开发环境

## 1. Purpose / 目的

**English:** This environment is the Week 2 foundation for the Vision, UI and Data workstream. It verifies that Python, OpenCV and Git work on Windows before the project is moved to Raspberry Pi OS.

**中文：** 本环境是 Vision、UI 和 Data 工作流的第二周基础。它先在 Windows 上验证 Python、OpenCV 和 Git，再把项目迁移到 Raspberry Pi OS。

**English:** The current check uses a synthetic filament image, so it does not require a camera. A JPEG or PNG captured by the ESP32S3 Sense can be supplied later through the same command-line interface.

**中文：** 当前自检使用合成线材图像，因此不需要相机。后续可通过同一个命令行接口输入 ESP32S3 Sense 拍摄的 JPEG 或 PNG 图像。

## 2. Installed Tools / 已安装工具

**English:** The computer has Python 3.12.10, pip 25.0.1 and Git 2.54.0. The project uses a local `.venv` virtual environment so packages do not modify the global Python installation.

**中文：** 当前电脑已安装 Python 3.12.10、pip 25.0.1 和 Git 2.54.0。项目使用本地 `.venv` 虚拟环境，避免依赖包修改全局 Python 环境。

## 3. Setup Commands / 安装命令

**English:** Run the following commands in PowerShell from the project folder.

**中文：** 在项目文件夹中打开 PowerShell，然后运行以下命令。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**English:** If the default Python package index is unusually slow in China, use the same locked file with the Tsinghua mirror.

**中文：** 如果在中国访问默认 Python 软件源速度异常缓慢，可使用同一个固定版本文件和清华镜像安装。

```powershell
.\.venv\Scripts\python.exe -m pip install `
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple `
  -r requirements.txt
```

## 4. Verification / 验证

**English:** Run the automatic tests and the OpenCV image check.

**中文：** 运行自动测试和 OpenCV 图像自检。

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe src\week2_opencv_check.py
```

**English:** A successful run prints `"status": "PASS"` and saves an annotated image to `data/output/week2_opencv_check.jpg`.

**中文：** 成功运行后会显示 `"status": "PASS"`，并把标注图像保存到 `data/output/week2_opencv_check.jpg`。

## 5. Test an ESP32S3 Sense Image / 测试 ESP32S3 Sense 图像

**English:** Copy a JPEG or PNG into `data/input`, then provide its path to the script.

**中文：** 将 JPEG 或 PNG 图像复制到 `data/input`，然后把路径传给脚本。

```powershell
.\.venv\Scripts\python.exe src\week2_opencv_check.py `
  --input data\input\esp32_sample.jpg `
  --output data\output\esp32_sample_annotated.jpg
```

**English:** This Week 2 script only proves image decoding and a basic edge/contour pipeline. It is not yet a validated defect detector and its contour count must not be reported as measurement performance.

**中文：** 第二周脚本只验证图像解码以及基础边缘/轮廓流程。它还不是经过验证的缺陷检测器，轮廓数量不能作为检测性能结果上报。

## 6. Git Workflow / Git 工作流

**English:** The repository is already initialised. Before the first commit, configure your real identity if Git does not already contain it.

**中文：** 仓库已经初始化。首次提交前，如果 Git 中尚未配置身份，请填写你的真实信息。

```powershell
git config user.name "Your Name"
git config user.email "your.email@example.com"
git status
git add .gitignore .gitattributes requirements.in requirements.txt src tests data WEEK2_ENVIRONMENT_EN-ZH.md
git commit -m "Set up Week 2 Python and OpenCV environment"
```

**English:** Do not copy `.venv` into Git. The pinned `requirements.txt` file is sufficient to recreate the environment on another Windows computer or, after platform testing, on Raspberry Pi OS.

**中文：** 不要将 `.venv` 提交到 Git。固定版本的 `requirements.txt` 足以在另一台 Windows 电脑上重建环境；经过平台兼容性测试后，也可用于 Raspberry Pi OS。

## 7. Week 2 Completion Evidence / 第二周完成证据

**English:** Retain the following evidence for the team log: software version output, passing pytest output, the generated annotated image, and the first Git commit hash.

**中文：** 团队日志应保留以下证据：软件版本输出、pytest 通过结果、生成的标注图像，以及第一次 Git 提交的哈希值。
