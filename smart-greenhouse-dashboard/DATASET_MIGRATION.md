# 草莓成熟度数据集导入与统一管理

## 功能

- 导入公开草莓成熟度 YOLO 数据集
- 统一映射为 `unripe / halfripe / ripe`
- 支持 MySQL 持久化，未配置时自动降级为内存模式
- 提供数据集列表、样本预览、启用切换

## MySQL 配置

任选一种：

### 1) 连接串

```bash
export MYSQL_URL="mysql://user:password@127.0.0.1:3306/smart_greenhouse_dashboard"
```

### 2) 分项配置

```bash
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password
export MYSQL_DATABASE=smart_greenhouse_dashboard
```

## 使用方式

1. 启动后端
2. 打开 `http://localhost:3000/#/datasets`
3. 填写公开数据集本地路径
4. 点击“开始导入”

## 公开数据集约定

支持常见 YOLO 结构：

```text
dataset/
  data.yaml
  images/train|val|test
  labels/train|val|test
```

系统会把公开数据集中的成熟度类别统一归一为：

- `unripe`
- `halfripe`
- `ripe`

## 说明

- 没有配置 MySQL 时，数据会保存在进程内存中
- 当前实现优先保证“导入、统一、查看”可用
