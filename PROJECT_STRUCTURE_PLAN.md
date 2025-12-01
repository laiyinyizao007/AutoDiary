# 项目结构整理方案

## 现状分析
根目录散布着大量文件：
- 📄 20+ 个 Markdown 文档（部署、测试、修复报告）
- 🐍 15+ 个 Python 脚本（服务器、工具、测试）
- ⚙️ 配置文件混乱（platformio.ini, config.json 等）
- 📋 日志和临时文件

## 整理后的推荐结构

```
AutoDiary/
├── README.md                          # 项目总说明
├── .gitignore                        # Git 忽略文件
├── AutoDiary.code-workspace          # VS Code 工作区
├── .claude/                          # Claude 项目初始化文件（新增）
│   ├── project.json                  # 项目配置
│   └── claude_config.json            # Claude 助手配置
│
├── docs/                             # 📚 文档目录（新增）
│   ├── DEPLOYMENT/                   # 部署文档
│   │   ├── DEPLOYMENT_AND_TESTING_GUIDE.md
│   │   ├── DEPLOYMENT_CHECKLIST.md
│   │   ├── QUICK_DEPLOYMENT_GUIDE.md
│   │   └── ...
│   ├── GUIDES/                       # 指南文档
│   │   ├── QUICK_START_GUIDE.md
│   │   ├── IMPLEMENTATION_GUIDE.md
│   │   └── VERIFICATION_GUIDE.md
│   ├── ARCHITECTURE/                 # 架构文档
│   │   ├── ARCHITECTURE_COMPARISON.md
│   │   ├── INTEGRATION_PLAN.md
│   │   └── PROJECT_SUMMARY.md
│   ├── TROUBLESHOOTING/              # 故障排除
│   │   ├── CAMERA_TEST_DIAGNOSIS.md
│   │   ├── WEBSOCKET_ISSUE_ANALYSIS.md
│   │   ├── WIFI_CONNECTION_TEST.md
│   │   └── ...
│   └── REPORTS/                      # 测试报告
│       ├── EXECUTION_AND_TEST_REPORT.md
│       ├── HARDWARE_FINAL_TEST_REPORT.md
│       ├── END_TO_END_TEST_RESULTS.md
│       └── ...
│
├── scripts/                          # 🐍 Python 脚本目录（新增）
│   ├── servers/                      # 服务器脚本
│   │   ├── server.py
│   │   ├── integrated_server.py
│   │   ├── http_server.py
│   │   ├── camera_web_server.py
│   │   └── hardware_test_server.py
│   ├── tools/                        # 工具脚本
│   │   ├── checkpoint_collector.py
│   │   ├── intelligent_analyzer.py
│   │   ├── realtime_monitor.py
│   │   └── fault_diagnostics.py
│   ├── deployment/                   # 部署脚本
│   │   ├── deploy_firmware.py
│   │   └── run_complete_workflow.py
│   ├── test/                         # 测试脚本
│   │   ├── test_camera_functionality.py
│   │   ├── test_connection.py
│   │   └── hardware_simulator.py
│   └── legacy/                       # 旧版本和备用脚本
│       ├── compatible_websocket_server.py
│       ├── simple_websocket_test_server.py
│       └── funasr_client.py
│
├── config/                           # ⚙️ 配置文件目录（新增）
│   ├── config.json                   # 主配置文件
│   ├── platformio.ini                # PlatformIO 配置
│   ├── platformio_fixed.ini
│   ├── docker-compose.yml            # Docker 配置
│   ├── Dockerfile
│   └── .env.example                  # 环境变量示例
│
├── src/                              # 源代码（已有）
│   ├── main.cpp                      # ESP32 主程序
│   ├── main_optimized.cpp            # 优化版本
│   ├── main_with_checkpoints.cpp     # 带检查点版本
│   └── *.bak                         # 备份
│
├── include/                          # 头文件（已有）
│   ├── camera_pins.h
│   └── README
│
├── lib/                              # 库文件（已有）
│   └── README
│
├── data/                             # 数据存储（已有）
│   ├── Images/
│   ├── Audio/
│   ├── AudioSegments/
│   ├── Transcriptions/
│   ├── Summaries/
│   ├── Analysis/
│   ├── Logs/
│   ├── checkpoints/
│   ├── diagnostics/
│   ├── Temp/
│   ├── test_audio/
│   ├── test_images/
│   └── real_test/
│
├── test/                            # 测试结果（已有）
│   ├── README
│   └── test_report_*.json
│
├── static/                          # Web 静态资源（已有）
│   └── images/
│
├── test_results/                    # 测试报告目录（已有）
│   └── test_report_*.json
│
├── requirements.txt                 # Python 依赖（在config目录）
├── deploy.bat                       # 部署脚本（在config目录）
├── deploy.sh
├── docker-test.sh
├── start_server.bat
└── .gitignore                       # 忽略配置
```

## 整理步骤

### 第一阶段：创建目录结构
- [ ] 创建 `.claude/` 目录
- [ ] 创建 `docs/` 及其子目录
- [ ] 创建 `scripts/` 及其子目录
- [ ] 创建 `config/` 目录

### 第二阶段：移动文件
- [ ] 移动所有 Markdown 文档到 `docs/`
- [ ] 移动所有 Python 脚本到 `scripts/`
- [ ] 移动配置文件到 `config/`
- [ ] 整理脚本文件（.bat, .sh）到 `config/`

### 第三阶段：清理和优化
- [ ] 删除根目录日志文件
- [ ] 整理备份文件
- [ ] 创建 Claude 配置文件
- [ ] 更新 .gitignore

### 第四阶段：验证和文档
- [ ] 验证所有路径引用正确
- [ ] 更新项目文档
- [ ] 创建文件映射说明

## 优势
✅ 清晰的项目结构
✅ 便于维护和查找文件
✅ 支持 Claude 和 IDE 索引
✅ 符合业界最佳实践
✅ 易于版本控制和协作
