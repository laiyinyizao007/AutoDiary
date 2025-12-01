# 参考项目流程分析与埋点方案

## 参考项目架构

基于 `Camera_HTTP_Server_STA.ino` 的分析

### 核心流程

```
┌─────────────────────────────────────────────────────────┐
│                    参考项目流程                          │
└─────────────────────────────────────────────────────────┘

  ┌──────────────┐
  │  用户请求    │
  │ /capture     │
  │ 或 /save     │
  └──────┬───────┘
         │
         ▼
  ┌──────────────────────────┐
  │ 1. 标记动作标志          │
  │ takeNewPhoto=true        │
  │ 返回 200 OK              │
  └──────┬───────────────────┘
         │ (立即返回给客户端)
         │
    ┌────┴─────────┐
    │              │
    ▼              ▼
┌─────────────┐ ┌──────────────────┐
│ SPIFFS      │ │ SD Card          │
│ 预览用      │ │ 永久存储         │
└─────────────┘ └──────────────────┘
    │              │
    ▼              ▼
 capturePhotoSaveSpiffs()  photo_save()
```

---

## 详细步骤分析

### 步骤 1: 拍摄 (Capture)

**参考代码位置**: `capturePhotoSaveSpiffs()`

```cpp
void capturePhotoSaveSpiffs( void ) {
  camera_fb_t * fb = NULL;
  
  do {
    // 步骤 1.1: 获取帧缓冲
    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed");
      return;
    }
    // 此时: 帧数据在内存中 (PSRAM)
    
    // 步骤 1.2: 打开文件
    File file = SPIFFS.open(FILE_PHOTO, FILE_WRITE);
    
    // 步骤 1.3: 写入数据
    file.write(fb->buf, fb->len);
    
    // 步骤 1.4: 获取文件大小
    int fileSize = file.size();
    
    // 步骤 1.5: 关闭文件
    file.close();
    
    // 步骤 1.6: 释放帧缓冲
    esp_camera_fb_return(fb);
    
    // 步骤 1.7: 验证文件
    ok = checkPhoto(SPIFFS);
  } while ( !ok );
}
```

**缺陷分析**:
- ❌ 无埋点信息
- ❌ 无耗时统计
- ❌ 无内存释放验证
- ❌ 无上传功能
- ❌ 无文件删除逻辑

### 步骤 2: 存储 (Storage)

**SPIFFS 存储**:
```cpp
File file = SPIFFS.open(FILE_PHOTO, FILE_WRITE);
file.write(fb->buf, fb->len);
fileSize = file.size();
file.close();
```

**SD 卡存储** (在 `photo_save()` 中):
```cpp
writeFile(SD, fileName, fb->buf, fb->len);

void writeFile(fs::FS &fs, const char * path, uint8_t * data, size_t len){
    File file = fs.open(path, FILE_WRITE);
    file.write(data, len);
    file.close();
}
```

### 步骤 3: 上传 (Upload)

**参考代码中**: 不存在上传功能，只有本地保存

**所需补充**:
- HTTP POST 到服务器
- 上传进度报告
- 上传失败重试
- 上传成功验证

### 步骤 4: 删除 (Delete)

**参考代码中**: 不存在删除功能，所有文件都保留

### 步骤 5: 释放内存 (Memory Release)

**参考代码**:
```cpp
esp_camera_fb_return(fb);  // 释放帧缓冲
file.close();              // 关闭文件
```

---

## 改进的完整流程与埋点

### 核心指标定义

```cpp
// 阶段标识
enum UploadPhase {
    PHASE_IDLE,           // 0: 空闲
    PHASE_CAPTURING,      // 1: 正在拍摄
    PHASE_STORING,        // 2: 正在存储
    PHASE_UPLOADING,      // 3: 正在上传
    PHASE_CLEANUP,        // 4: 清理中
    PHASE_COMPLETE,       // 5: 完成
    PHASE_ERROR           // 6: 错误
};

// 埋点数据结构
struct UploadCheckpoint {
    unsigned long timestamp;      // 时间戳
    UploadPhase phase;           // 当前阶段
    uint32_t free_heap;          // 剩余堆内存
    uint32_t free_psram;         // 剩余 PSRAM
    int frame_size;              // 帧大小
    int file_size;               // 文件大小
    unsigned long elapsed_ms;    // 耗时（毫秒）
    const char* message;         // 状态消息
};
```

### 流程图与埋点位置

```
开始
  │
  ▼ [埋点1] 时刻: 拍摄开始
┌─────────────────────────────┐
│ CAPTURE PHASE               │
│ ├─ timestamp                │ [埋点2] 获取帧
│ ├─ free_heap_before         │ [埋点3] 帧大小
│ ├─ frame_size               │
└────────┬────────────────────┘
         │
         ▼ [埋点4] 时刻: 存储开始
┌─────────────────────────────┐
│ STORAGE PHASE               │
│ ├─ open file                │ [埋点5] 文件打开成功
│ ├─ write data               │ [埋点6] 写入完成
│ ├─ file_size                │
│ ├─ verify file              │ [埋点7] 验证成功
│ ├─ free_heap_after_storage  │
└────────┬────────────────────┘
         │
         ▼ [埋点8] 时刻: 上传开始
┌─────────────────────────────┐
│ UPLOAD PHASE                │
│ ├─ http post                │ [埋点9] 上传进度
│ ├─ response check           │ [埋点10] 上传完成
│ ├─ upload_time              │
│ └─ free_heap_after_upload   │
└────────┬────────────────────┘
         │
         ▼ [埋点11] 时刻: 清理开始
┌─────────────────────────────┐
│ CLEANUP PHASE               │
│ ├─ delete file              │ [埋点12] 文件删除
│ ├─ release buffer           │ [埋点13] 缓冲释放
│ └─ final_free_heap          │
└────────┬────────────────────┘
         │
         ▼ [埋点14] 时刻: 流程完成
       SUCCESS
```

---

## 建议的埋点详细内容

### 埋点 1: 拍摄开始

```cpp
Serial.printf("📸 CHECKPOINT_1_CAPTURE_START\n");
Serial.printf("  timestamp: %lu\n", millis());
Serial.printf("  phase: CAPTURING\n");
Serial.printf("  free_heap: %d bytes\n", esp_get_free_heap_size());
Serial.printf("  free_psram: %d bytes\n", esp_psram_get_free_size());
```

### 埋点 2: 帧获取成功

```cpp
Serial.printf("📸 CHECKPOINT_2_FRAME_GET_SUCCESS\n");
Serial.printf("  frame_size: %d bytes\n", fb->len);
Serial.printf("  elapsed_ms: %lu\n", millis() - capture_start);
```

### 埋点 3: 存储开始

```cpp
Serial.printf("💾 CHECKPOINT_3_STORAGE_START\n");
Serial.printf("  filename: %s\n", FILE_PHOTO);
Serial.printf("  phase: STORING\n");
```

### 埋点 4: 存储完成

```cpp
Serial.printf("💾 CHECKPOINT_4_STORAGE_SUCCESS\n");
Serial.printf("  file_size: %d bytes\n", file.size());
Serial.printf("  storage_time: %lu ms\n", millis() - storage_start);
Serial.printf("  free_heap: %d bytes\n", esp_get_free_heap_size());
```

### 埋点 5: 上传开始

```cpp
Serial.printf("📤 CHECKPOINT_5_UPLOAD_START\n");
Serial.printf("  phase: UPLOADING\n");
Serial.printf("  target_url: %s\n", upload_url);
Serial.printf("  file_size: %d bytes\n", file_size);
```

### 埋点 6: 上传完成

```cpp
Serial.printf("📤 CHECKPOINT_6_UPLOAD_SUCCESS\n");
Serial.printf("  http_code: %d\n", response_code);
Serial.printf("  upload_time: %lu ms\n", millis() - upload_start);
Serial.printf("  response_body: %s\n", response_body);
```

### 埋点 7: 删除完成

```cpp
Serial.printf("🗑️ CHECKPOINT_7_DELETE_SUCCESS\n");
Serial.printf("  deleted_file: %s\n", FILE_PHOTO);
Serial.printf("  phase: CLEANUP\n");
```

### 埋点 8: 内存释放

```cpp
Serial.printf("🔄 CHECKPOINT_8_MEMORY_RELEASE\n");
Serial.printf("  esp_camera_fb_return: done\n");
Serial.printf("  file_close: done\n");
Serial.printf("  free_heap_before: %d bytes\n", before_release);
Serial.printf("  free_heap_after: %d bytes\n", after_release);
Serial.printf("  recovered: %d bytes\n", after_release - before_release);
```

### 埋点 9: 完成总结

```cpp
Serial.printf("✅ CHECKPOINT_9_COMPLETE\n");
Serial.printf("  total_time: %lu ms\n", millis() - total_start);
Serial.printf("  phases: CAPTURE(%lu) -> STORAGE(%lu) -> UPLOAD(%lu) -> CLEANUP(%lu)\n",
              capture_time, storage_time, upload_time, cleanup_time);
Serial.printf("  memory_delta: %d bytes\n", final_heap - initial_heap);
Serial.printf("  status: SUCCESS\n");
```

---

## JSON 埋点日志格式

**建议的 JSON 日志格式**:

```json
{
  "checkpoint": {
    "id": 1,
    "phase": "CAPTURE_START",
    "timestamp": 1704067200000,
    "elapsed_ms": 0,
    "memory": {
      "free_heap": 245632,
      "free_psram": 4087808
    },
    "details": {
      "action": "Starting photo capture sequence"
    }
  }
}
```

**完整流程日志示例**:

```json
[
  {
    "checkpoint": 1,
    "phase": "CAPTURE_START",
    "timestamp": 1704067200000,
    "elapsed_from_start": 0
  },
  {
    "checkpoint": 2,
    "phase": "FRAME_GET_SUCCESS",
    "timestamp": 1704067200234,
    "elapsed_from_start": 234,
    "frame_size": 18432
  },
  {
    "checkpoint": 3,
    "phase": "STORAGE_START",
    "timestamp": 1704067200235,
    "elapsed_from_start": 235,
    "filename": "/photo.jpg"
  },
  {
    "checkpoint": 4,
    "phase": "STORAGE_SUCCESS",
    "timestamp": 1704067200456,
    "elapsed_from_start": 456,
    "file_size": 18432,
    "storage_time": 221
  },
  {
    "checkpoint": 5,
    "phase": "UPLOAD_START",
    "timestamp": 1704067200457,
    "elapsed_from_start": 457,
    "target_url": "http://192.168.1.100:8080/upload"
  },
  {
    "checkpoint": 6,
    "phase": "UPLOAD_SUCCESS",
    "timestamp": 1704067201234,
    "elapsed_from_start": 1234,
    "http_code": 200,
    "upload_time": 777
  },
  {
    "checkpoint": 7,
    "phase": "DELETE_SUCCESS",
    "timestamp": 1704067201235,
    "elapsed_from_start": 1235,
    "deleted_file": "/photo.jpg"
  },
  {
    "checkpoint": 8,
    "phase": "MEMORY_RELEASE",
    "timestamp": 1704067201236,
    "elapsed_from_start": 1236,
    "free_heap_before": 227200,
    "free_heap_after": 245632,
    "recovered": 18432
  },
  {
    "checkpoint": 9,
    "phase": "COMPLETE",
    "timestamp": 1704067201237,
    "elapsed_from_start": 1237,
    "total_time": 1237,
    "status": "SUCCESS"
  }
]
```

---

## 参考项目改进建议总结

| 方面 | 参考项目 | 改进方案 |
|-----|---------|--------|
| 拍摄 | ✅ 完整实现 | 添加埋点和性能指标 |
| 存储 | ✅ SPIFFS/SD | 添加验证和恢复 |
| 上传 | ❌ 不存在 | 需要实现 HTTP POST |
| 删除 | ❌ 不存在 | 需要实现清理逻辑 |
| 埋点 | ❌ 无埋点 | 添加详细埋点 |
| 内存监控 | ❌ 无 | 添加内存跟踪 |
| 错误处理 | 基础 | 改进重试和恢复 |
| 进度报告 | ❌ 无 | 添加进度回调 |

---

## 下一步行动

1. ✅ 基于参考项目的框架
2. ✅ 添加完整的埋点
3. ✅ 实现上传功能
4. ✅ 添加清理和释放逻辑
5. ✅ 创建监控仪表盘
