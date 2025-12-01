# 🏗️ AutoDiary 项目结构整理指南

## 📊 当前状态

根目录散布着大量文件，需要整理为更清晰的结构。

### 现有文件统计
- 📄 **Markdown 文档**: 20+ 个
- 🐍 **Python 脚本**: 15+ 个  
- ⚙️ **配置文件**: 10+ 个
- 📋 **日志和临时文件**: 6+ 个

---

## 🎯 目标结构

整理后的项目将采用以下结构：

```
AutoDiary/
├── .claude/                    # ✅ Claude 初始化配置（已创建）
│   └── project.json
├── docs/                       # 📚 文档目录（需创建）
│   ├── DEPLOYMENT/
│   ├── GUIDES/
│   ├── ARCHITECTURE/
│   ├── TROUBLESHOOTING/
│   └── REPORTS/
├── scripts/                    # 🐍 脚本目录（需创建）
│   ├── servers/
│   ├── tools/
│   ├── deployment/
│   ├── test/
│   └── legacy/
├── config/                     # ⚙️ 配置目录（需创建）
├── src/                        # 📝 源代码（已有）
├── include/                    # 📚 头文件（已有）
├── data/                       # 📦 数据目录（已有）
└── static/                     # 🎨 Web 资源（已有）
```

---

## 📋 手动整理步骤

### 第一步：创建目录结构

在 VS Code 终端或 PowerShell 中执行：

```powershell
# 创建所有必要的目录
mkdir docs\DEPLOYMENT, docs\GUIDES, docs\ARCHITECTURE, docs\TROUBLESHOOTING, docs\REPORTS
mkdir scripts\servers, scripts\tools, scripts\deployment, scripts\test, scripts\legacy
mkdir config
```

### 第二步：移动 Markdown 文档

#### 部署文档 → `docs/DEPLOYMENT/`
```
DEPLOYMENT_AND_TESTING_GUIDE.md
DEPLOYMENT_CHECKLIST.md
DEPLOYMENT_COMPLETION_SUMMARY.md
QUICK_DEPLOYMENT_GUIDE.md
DOCKER_DEPLOYMENT_GUIDE.md
```

#### 指南文档 → `docs/GUIDES/`
```
QUICK_START_GUIDE.md
IMPLEMENTATION_GUIDE.md
VERIFICATION_GUIDE.md
MIGRATION_GUIDE.md
```

#### 架构文档 → `docs/ARCHITECTURE/`
```
ARCHITECTURE_COMPARISON.md
INTEGRATION_PLAN.md
PROJECT_SUMMARY.md
REFERENCE_ANALYSIS.md
```

#### 故障排除 → `docs/TROUBLESHOOTING/`
```
CAMERA_TEST_DIAGNOSIS.md
WEBSOCKET_ISSUE_ANALYSIS.md
WEBSOCKET_FIX_COMPLETE.md
WIFI_CONNECTION_TEST.md
WIFI_CONNECTION_TEST_FINAL_REPORT.md
CPP_SERVER_CRASH_FIX.md
FIX_SUMMARY.md
HTTP_MIGRATION_COMPLETE.md
RESTART_AND_CHECK.md
```

#### 测试报告 → `docs/REPORTS/`
```
EXECUTION_AND_TEST_REPORT.md
HARDWARE_FINAL_TEST_REPORT.md
HARDWARE_COMPILE_TEST_REPORT.md
END_TO_END_TEST_RESULTS.md
FINAL_DEPLOYMENT_REPORT.md
COMPLETION_SUMMARY.md
```

### 第三步：移动 Python 脚本

#### 服务器脚本 → `scripts/servers/`
```
server.py
integrated_server.py
http_server.py
camera_web_server.py
hardware_test_server.py
```

#### 工具脚本 → `scripts/tools/`
```
checkpoint_collector.py
intelligent_analyzer.py
realtime_monitor.py
fault_diagnostics.py
```

#### 部署脚本 → `scripts/deployment/`
```
deploy_firmware.py
run_complete_workflow.py
```

#### 测试脚本 → `scripts/test/`
```
test_camera_functionality.py
test_connection.py
hardware_simulator.py
```

#### 旧版脚本 → `scripts/legacy/`
```
compatible_websocket_server.py
compatible_websocket_server_v2.py
simple_websocket_test_server.py
simple_test_server.py
test_server.py
funasr_client.py
fixed_websocket_server.py
```

### 第四步：移动配置文件

所有以下文件移动到 `config/`：
```
config.json
platformio.ini
platformio_fixed.ini
docker-compose.yml
Dockerfile
deploy.bat
deploy.sh
start_server.bat
docker-test.sh
requirements.txt
requirements_new.txt
```

### 第五步：清理日志和临时文件

移动到 `data/Logs/`：
```
autodiary_server.log
integrated_server.log
websocket_compatible_server.log
deployment_log.txt
```

删除临时文件：
```
test_checkpoint_data.json
test_frame.jpg
```

---

## 🤖 自动化整理

如果想使用脚本自动整理，运行：

```bash
python organize_project.py
```

该脚本会自动：
1. ✅ 创建所有目录
2. ✅ 移动所有文件到对应位置
3. ✅ 清理根目录日志
4. ✅ 保留核心文件在根目录

---

## ✅ 整理后需要更新的文件

### 1. `.gitignore`
确保添加以下内容（如果还没有）：
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/

# PlatformIO
.pio/
.vscode/
build/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Data
data/Logs/*.log
data/Temp/*
*.json.bak

# Node (如果有)
node_modules/
```

### 2. 更新 Python 脚本中的导入路径

如果有脚本互相导入，需要更新相对路径。例如：

**旧**: `from server import WebSocketHandler`
**新**: `from scripts.servers.server import WebSocketHandler`

### 3. 更新 README.md

更新所有文件路径引用，例如：
```markdown
# 原来
pip install -r requirements.txt
python server.py

# 现在
pip install -r config/requirements.txt
python scripts/servers/server.py
```

### 4. 更新 PlatformIO 配置

编辑 `config/platformio.ini`，确保路径正确：
```ini
[platformio]
src_dir = src
include_dir = include
lib_dir = lib
data_dir = data
```

---

## 📚 建立的优势

整理后的好处：

✅ **清晰的项目结构**
- 一眼就能找到需要的文件
- 易于新成员快速理解项目

✅ **便于维护和扩展**
- 添加新功能时知道放在哪里
- 减少文件查找时间

✅ **支持 IDE 和工具索引**
- 更好的代码补全
- 正确的依赖分析

✅ **符合业界最佳实践**
- 标准的项目组织方式
- 易于与其他开发者协作

✅ **易于版本控制**
- 更清晰的 Git 提交
- 减少无关文件跟踪

---

## 🔧 整理完成后的验证

运行以下命令验证结构是否正确：

```bash
# 检查目录结构
tree /F /A

# 验证 Python 脚本可以找到模块
python -c "import sys; sys.path.insert(0, '.'); from scripts.servers import server; print('✓ 导入成功')"

# 验证配置文件在正确位置
ls config/
```

---

## 💡 可选：创建软链接或符号链接

对于仍需在根目录快速访问的文件，可以创建软链接：

```powershell
# PowerShell (管理员)
New-Item -ItemType SymbolicLink -Path ".\server.py" -Target ".\scripts\servers\server.py"
New-Item -ItemType SymbolicLink -Path ".\config.json" -Target ".\config\config.json"
```

---

## 📞 帮助

如有问题，检查：
1. 所有路径是否使用正斜杠 `/` 或双反斜杠 `\\`
2. Python 脚本中的 `sys.path` 是否正确配置
3. 文件是否真的移动到了新位置

---

**祝整理顺利！** 🎉
