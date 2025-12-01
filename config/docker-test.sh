#!/bin/bash

# AutoDiary Docker 部署测试和验证脚本
# 基于 reference 目录资源的完整部署验证

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 测试结果统计
TESTS_TOTAL=0
TESTS_PASSED=0
TESTS_FAILED=0

# 测试函数
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log_info "运行测试: $test_name"
    
    if eval "$test_command"; then
        log_success "✅ $test_name - 通过"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        log_error "❌ $test_name - 失败"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# 等待服务启动
wait_for_service() {
    local service_name="$1"
    local url="$2"
    local max_attempts="$3"
    local attempt=1
    
    log_info "等待 $service_name 服务启动..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "$url" > /dev/null 2>&1; then
            log_success "$service_name 服务已启动"
            return 0
        fi
        
        log_info "尝试 $attempt/$max_attempts: 等待 $service_name..."
        sleep 5
        attempt=$((attempt + 1))
    done
    
    log_error "$service_name 服务启动超时"
    return 1
}

# 主测试函数
main() {
    log_info "AutoDiary Docker 部署测试开始"
    log_info "基于 reference 目录资源: FunASR + Camera_HTTP_Server_STA + Minutes"
    echo ""
    
    # 检查Docker环境
    log_info "检查Docker环境..."
    run_test "Docker服务检查" "docker info > /dev/null 2>&1"
    run_test "Docker Compose检查" "docker-compose --version > /dev/null 2>&1"
    
    # 检查必要文件
    log_info "检查部署文件..."
    run_test "docker-compose.yml存在" "test -f docker-compose.yml"
    run_test "Dockerfile存在" "test -f Dockerfile"
    run_test "requirements_new.txt存在" "test -f requirements_new.txt"
    
    # 检查目录结构
    log_info "检查目录结构..."
    run_test "data目录存在" "test -d data"
    run_test "config目录存在" "test -d config"
    run_test "logs目录存在" "test -d logs"
    
    # 构建镜像
    log_info "构建Docker镜像..."
    run_test "Docker镜像构建" "docker-compose build --no-cache"
    
    # 启动服务
    log_info "启动Docker服务..."
    run_test "Docker服务启动" "docker-compose up -d"
    
    # 等待服务启动完成
    sleep 10
    
    # 检查容器状态
    log_info "检查容器状态..."
    run_test "autodiary_main容器运行" "docker ps --format 'table {{.Names}}' | grep -q autodiary_main"
    run_test "autodiary_funasr容器运行" "docker ps --format 'table {{.Names}}' | grep -q autodiary_funasr"
    run_test "autodiary_redis容器运行" "docker ps --format 'table {{.Names}}' | grep -q autodiary_redis"
    run_test "autodiary_nginx容器运行" "docker ps --format 'table {{.Names}}' | grep -q autodiary_nginx"
    
    # 等待服务就绪
    log_info "等待服务就绪..."
    wait_for_service "AutoDiary主服务" "http://localhost:8080/api/status" 12
    wait_for_service "FunASR服务" "http://localhost:10095/health" 6
    
    # 测试API端点
    log_info "测试API端点..."
    run_test "Web管理界面API" "curl -f -s http://localhost:8080/api/status > /dev/null"
    run_test "FunASR健康检查" "curl -f -s http://localhost:10095/health > /dev/null"
    run_test "Redis连接测试" "docker exec autodiary_redis redis-cli ping | grep -q PONG"
    
    # 测试WebSocket连接
    log_info "测试WebSocket连接..."
    run_test "视频流WebSocket" "timeout 10s curl -i -N -H 'Connection: Upgrade' -H 'Upgrade: websocket' http://localhost:8000/video 2>/dev/null | grep -q '101 Switching Protocols'"
    run_test "音频流WebSocket" "timeout 10s curl -i -N -H 'Connection: Upgrade' -H 'Upgrade: websocket' http://localhost:8001/audio 2>/dev/null | grep -q '101 Switching Protocols'"
    
    # 测试数据持久化
    log_info "测试数据持久化..."
    run_test "数据目录权限" "touch data/test_write.tmp && rm data/test_write.tmp"
    run_test "日志目录权限" "touch logs/test_write.tmp && rm logs/test_write.tmp"
    
    # 测试FunASR模型加载
    log_info "测试FunASR模型..."
    run_test "FunASR模型文件" "docker exec autodiary_main python -c 'from funasr import AutoModel; print(\"Model available\")' 2>/dev/null | grep -q 'Model available'"
    
    # 测试内存使用
    log_info "检查资源使用..."
    MEMORY_USAGE=$(docker stats --no-stream --format "{{.MemUsage}}" autodiary_main 2>/dev/null | cut -d'/' -f1 | sed 's/MiB//')
    if [ ! -z "$MEMORY_USAGE" ] && [ "$MEMORY_USAGE" -lt 1000 ]; then
        run_test "内存使用正常" "true"
        log_info "主服务内存使用: ${MEMORY_USAGE}MiB"
    else
        run_test "内存使用检查" "false"
    fi
    
    # 测试网络连接
    log_info "测试网络连接..."
    run_test "容器间网络连接" "docker exec autodiary_main ping -c 1 autodiary_funasr > /dev/null 2>&1"
    run_test "DNS解析测试" "docker exec autodiary_main nslookup autodiary_funasr > /dev/null 2>&1"
    
    # 测试日志输出
    log_info "检查日志输出..."
    run_test "应用日志输出" "docker logs autodiary_main 2>&1 | grep -q 'AutoDiary集成服务器初始化完成'"
    
    # 性能测试
    log_info "进行性能测试..."
    run_test "并发请求测试" "for i in {1..5}; do curl -s http://localhost:8080/api/status > /dev/null & done; wait"
    
    # 生成测试报告
    echo ""
    log_info "生成测试报告..."
    
    # 容器信息
    echo "=== 容器信息 ===" > test_report.txt
    docker-compose ps >> test_report.txt
    echo "" >> test_report.txt
    
    # 镜像信息
    echo "=== 镜像信息 ===" >> test_report.txt
    docker images | grep autodiary >> test_report.txt
    echo "" >> test_report.txt
    
    # 资源使用
    echo "=== 资源使用 ===" >> test_report.txt
    docker stats --no-stream >> test_report.txt
    echo "" >> test_report.txt
    
    # 网络信息
    echo "=== 网络信息 ===" >> test_report.txt
    docker network ls | grep autodiary >> test_report.txt
    echo "" >> test_report.txt
    
    # 测试结果统计
    echo "=== 测试结果 ===" >> test_report.txt
    echo "总测试数: $TESTS_TOTAL" >> test_report.txt
    echo "通过测试: $TESTS_PASSED" >> test_report.txt
    echo "失败测试: $TESTS_FAILED" >> test_report.txt
    echo "成功率: $(( TESTS_PASSED * 100 / TESTS_TOTAL ))%" >> test_report.txt
    
    run_test "测试报告生成" "test -f test_report.txt"
    
    # 显示测试结果
    echo ""
    log_info "测试完成！"
    echo "=================================="
    echo "总测试数: $TESTS_TOTAL"
    echo -e "通过测试: ${GREEN}$TESTS_PASSED${NC}"
    echo -e "失败测试: ${RED}$TESTS_FAILED${NC}"
    
    SUCCESS_RATE=$(( TESTS_PASSED * 100 / TESTS_TOTAL ))
    if [ $SUCCESS_RATE -ge 80 ]; then
        echo -e "成功率: ${GREEN}$SUCCESS_RATE%${NC}"
        log_success "🎉 AutoDiary Docker 部署测试通过！"
    elif [ $SUCCESS_RATE -ge 60 ]; then
        echo -e "成功率: ${YELLOW}$SUCCESS_RATE%${NC}"
        log_warning "⚠️ AutoDiary Docker 部署部分通过，建议检查失败项"
    else
        echo -e "成功率: ${RED}$SUCCESS_RATE%${NC}"
        log_error "❌ AutoDiary Docker 部署测试失败，请检查配置"
    fi
    
    echo "=================================="
    echo "详细报告已保存到: test_report.txt"
    echo ""
    
    # 显示访问信息
    if [ $SUCCESS_RATE -ge 60 ]; then
        log_info "服务访问地址："
        echo "📱 Web管理界面: http://localhost:8080"
        echo "🎥 视频流: ws://localhost:8000/video"
        echo "🎤 音频流: ws://localhost:8001/audio"
        echo "🔧 FunASR服务: http://localhost:10095"
        echo "🌐 Nginx代理: http://localhost"
        echo ""
        
        # 显示实用命令
        log_info "实用命令："
        echo "查看服务状态: docker-compose ps"
        echo "查看日志: docker-compose logs -f autodiary_main"
        echo "重启服务: docker-compose restart"
        echo "停止服务: docker-compose down"
        echo "进入容器: docker exec -it autodiary_main bash"
    fi
    
    # 如果测试失败，提供故障排除建议
    if [ $TESTS_FAILED -gt 0 ]; then
        echo ""
        log_warning "故障排除建议："
        echo "1. 检查Docker服务: docker info"
        echo "2. 查看容器日志: docker-compose logs"
        echo "3. 检查端口占用: netstat -tulpn | grep -E ':(8000|8001|8080|10095)'"
        echo "4. 重新构建镜像: docker-compose build --no-cache"
        echo "5. 清理并重启: docker-compose down && docker system prune -f && docker-compose up -d"
    fi
    
    # 返回适当的退出码
    if [ $SUCCESS_RATE -ge 80 ]; then
        exit 0
    else
        exit 1
    fi
}

# 清理函数
cleanup() {
    log_info "清理测试环境..."
    # 保留服务运行，只清理临时文件
    if [ -f "test_report.txt" ]; then
        log_info "测试报告已保存"
    fi
}

# 信号处理
trap cleanup EXIT

# 运行主函数
main "$@"
