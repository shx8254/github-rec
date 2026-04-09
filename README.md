# GitHub 推荐引擎 (GitHub Rec)

GitHub 本身不支持模糊搜索，也没有个性化推荐功能。对于关注特定技术方向的开发者来说，很难发现与已有 Star 项目相似的新项目。  
本项目正是为了解决这一痛点：**基于您 Star 过的仓库，自动推荐感兴趣的新项目，并过滤掉空仓库或无代码项目**。

## ✨ 主要特性

- 🔍 **基于 Star 历史推荐**：分析您已 Star 的仓库，提取关键信息（语言、主题、描述等）
- 🧠 **本地运行，隐私安全**：所有数据（包括 Token、Star 列表、推荐结果）均存储在本地，不依赖任何外部服务
- 🚫 **智能过滤**：自动排除空仓库、归档仓库、无代码项目（如纯文档/博客仓库）
- 📊 **可调推荐权重**：支持调整语言匹配、主题相似度、活跃度等维度的权重
- 🔄 **增量更新**：仅获取新的 Star 记录，避免重复拉取

## 🛠️ 技术栈

- Python 3.9+ 

## 📦 安装与使用

### 1. 获取 GitHub Token
前往 [GitHub Tokens](https://github.com/settings/tokens) 生成一个 `repo` 或 `public_repo` 权限的 Token（仅需读取 Star 列表）。

### 2. 克隆项目
```bash
git clone https://github.com/yourname/github-rec.git
cd github-rec
```

### 3. 安装依赖（Python 示例）
```
pip install -r requirements.txt
```

### 4. 配置 Token
复制配置文件模板：
```
cp config.example.json config.json
```
编辑 config.json：
```
{
  "github_token": "ghp_xxxxxxxxxxxx",
  "username": "你的GitHub用户名",
  "db_path": "./stars.db",
  "max_recommendations": 50
}
```

### 5. 运行推荐
```
python recommend.py
```

首次运行会拉取所有 Star 记录（可能需要几分钟），后续仅增量更新。
📁 数据存储结构（示例）
text
```
data/
├── stars.db          # SQLite 数据库
├── recommendations.json   # 推荐结果缓存
└── filters.log       # 过滤记录（空仓库/无代码项目）
```
## 🔧 配置项说明

| 参数 | 说明 |
|------|------|
| `github_token` | 用于调用 GitHub API 的 Token |
| `username` | 目标 GitHub 用户名 |
| `max_stars_to_scan` | 最多扫描多少条 Star 记录（0 表示全部） |
| `min_stars_threshold` | 推荐的仓库至少需要多少 Star（默认 10） |
| `exclude_topics` | 排除的主题列表（如 `tutorial`, `example`） |
| `exclude_languages` | 排除的编程语言（如 `HTML`, `CSS`） |

## 📈 推荐算法简述

1. **收集特征**：从用户 Star 列表中提取所有仓库的编程语言、Topic 标签、描述关键词。

2. **计算偏好向量**：统计高频语言和主题的权重（例如 Star 越近权重越高）。

3. **候选池生成**：从每个已 Star 仓库的“推荐相似仓库”接口或按语言搜索新仓库。

4. **评分与过滤**：
   - 语言匹配度（+5）
   - Topic 重叠数（每个 +2）
   - 描述关键词匹配（+1）
   - 仓库有 README（+1）
   - 最近三个月有更新（+2）
   - 空仓库或无代码（直接排除）

5. **排序输出**：取评分最高的 N 个仓库，去重后展示。

## 📝 输出示例

```text
===== 为你推荐以下 10 个仓库 =====

1. [Python] awesome-mlops ★1240
   https://github.com/awesome-mlops/awesome-mlops
   原因：与你的 star 仓库 "mlops-course" 语言/主题相似

2. [Rust] datafusion ★3780
   https://github.com/apache/datafusion
   原因：你 star 过 ballista、arrow-rs
```

## 🧹 过滤规则明细

- **空仓库**：大小为 0 KB 或无任何代码文件
- **无代码项目**：仅包含 `.md`、`.txt`、图片等非代码文件
- **归档仓库**：已设为 `archived=true`
- **模板仓库**：仓库类型为 `template`
