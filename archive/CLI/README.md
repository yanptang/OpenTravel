# Python CLI 开发示例

这个目录用一个很小的示例，说明什么是 Python CLI 开发，以及为什么 Agent 开发很适合先从 CLI 做起。

示例文件是 [CLI_example.py](./CLI_example.py)。
它是一个“个人健康助理”命令行程序，用户可以在终端里输入名字、体重和身高，程序会计算 BMI 并给出简单建议。

---

## 1. 什么是 CLI

CLI 是 Command Line Interface 的缩写，意思是“命令行界面”。

CLI 程序没有按钮和窗口，用户是在终端里通过命令来使用它：

```bash
python3 CLI_example.py --name 小明 --weight 60 --height 170
```

这个命令的意思是：

- 运行 `CLI_example.py`
- 传入名字、体重、身高
- 程序根据这些参数执行计算，并把结果打印到终端

CLI 的特点很直接：

- 输入明确
- 输出明确
- 适合自动化
- 适合调试
- 适合脚本串联

---

## 2. 为什么 Agent 开发适合 CLI

Agent 的本质是“输入一段文本，输出一段文本，必要时再调用工具”。

这和 CLI 的工作方式很像：

- CLI 接收参数
- 程序执行逻辑
- 输出结果到终端

对于 Agent 开发来说，CLI 有几个明显优势。

### 2.1 调试快

Agent 开发阶段最常见的事情不是“界面不好看”，而是：

- 参数有没有传对
- Prompt 有没有写对
- 模型输出是不是合法 JSON
- 工具调用有没有成功
- 哪一步报错了

这些问题在终端里最容易看清楚。

### 2.2 容易自动化

CLI 可以直接被脚本调用。

比如：

- 一个 CLI 负责抓取数据
- 一个 CLI 负责翻译
- 一个 CLI 负责整理输出

这些工具可以像流水线一样串起来。

### 2.3 适合开发者优先的阶段

很多 Agent 项目在早期主要是开发者和研究者在用。
这个阶段最重要的是：

- 能跑
- 能看日志
- 能复现问题
- 能快速修改

CLI 比 GUI 更符合这个阶段。

### 2.4 适合服务器或远程环境

很多 Agent 运行在服务器、容器或远程机器上。
这时候直接终端交互比做一套完整前端更高效。

---

## 3. 这个示例程序做了什么

这个示例是一个最小健康助理。

它会做三件事：

1. 读取命令行参数
2. 判断是否传入了体重和身高
3. 计算 BMI 并输出建议

如果没有传入体重或身高，它会提示用户补充信息。

---

## 4. 如何运行

先进入目录：

```bash
cd archive/CLI
```

然后直接运行：

```bash
python3 CLI_example.py --name 小明 --weight 60 --height 170
```

也可以先看帮助信息：

```bash
python3 CLI_example.py --help
```

如果想少传几个参数，也可以只传部分内容：

```bash
python3 CLI_example.py --name 小明
```

---

## 5. 运行结果大概是什么样

如果传入了体重和身高，程序会：

- 打印问候语
- 计算 BMI
- 根据 BMI 给出简单建议

如果没传体重或身高，程序会提示继续补充信息。

---

## 6. argparse 是什么

`argparse` 是 Python 标准库里的命令行参数解析工具。

它的作用是把用户在终端里输入的内容，解析成程序能直接使用的变量。

比如下面这条命令：

```bash
python3 CLI_example.py --name 小明 --weight 60 --height 170
```

`argparse` 会把它解析成：

- `name = "小明"`
- `weight = 60`
- `height = 170`

### 6.1 argparse 的基本流程

CLI 程序一般都按这个顺序写：

1. 创建解析器
2. 定义参数
3. 解析参数
4. 执行业务逻辑

对应到代码里，就是：

```python
parser = argparse.ArgumentParser(description="简单的个人健康助理 CLI")
parser.add_argument("-n", "--name", default="朋友", help="你的名字")
parser.add_argument("--weight", type=float, help="你的体重(kg)")
parser.add_argument("--height", type=float, help="你的身高(cm)")
args = parser.parse_args()
```

### 6.2 常见参数类型

- `--name` 这种带 `--` 的，一般是长参数
- `-n` 这种单短横线的，一般是短参数
- `type=float` 表示这个参数必须是数字
- `default="朋友"` 表示没传参数时用默认值

### 6.3 argparse 适合做什么

`argparse` 适合做：

- 接收输入参数
- 做基本校验
- 输出帮助信息
- 让 CLI 更像一个正式工具

---

## 7. 一般 CLI 项目怎么写

一个简单的 CLI 项目，通常会有这些部分：

### 7.1 一个入口文件

一般叫：

- `main.py`
- `app.py`
- `cli.py`

入口文件负责：

- 接收参数
- 调用业务逻辑
- 打印结果

### 7.2 一个业务模块

把真正的逻辑单独放出来，比如：

- 计算
- 调用模型
- 处理数据
- 生成文本

这样入口文件不会太乱。

### 7.3 一个参数解析模块

如果 CLI 稍微复杂一点，通常会把参数定义单独拆开。

例如：

- `args.py`
- `config.py`

这样更容易维护。

### 7.4 一个 README

README 至少要说明：

- 这是做什么的
- 怎么安装
- 怎么运行
- 参数是什么
- 输出是什么

---

## 8. 一个常见的 CLI 目录结构

```text
project/
  README.md
  requirements.txt
  main.py
  cli/
    __init__.py
    args.py
    logic.py
    utils.py
```

如果项目更大一点，可以拆成：

```text
project/
  README.md
  requirements.txt
  src/
    app/
      __init__.py
      main.py
      args.py
      service.py
      renderer.py
```

核心原则是：

- 入口文件只负责“接收和分发”
- 真正的逻辑放到独立模块
- 让代码结构和使用方式分开

---

## 9. 这个示例和 Agent 开发的关系

这个示例虽然只是一个 BMI 程序，但它展示了 Agent 开发里很基础、也很重要的思路：

- 用命令行接收输入
- 把输入变成结构化参数
- 执行确定性的逻辑
- 输出可读结果

OpenTravel 后面的本地 CLI 原型，其实就是把这个思路放大：

- 输入旅行需求
- 生成结构化行程
- 校验和修正结果
- 输出机器可处理的 JSON 和人类可读的文档

所以先理解 CLI，再理解 Agent，会更顺。

---

## 10. 这个目录里有哪些文件

- [CLI_example.py](./CLI_example.py)：示例程序
- [README.md](./README.md)：说明文档
- [tests/](./tests/)：最小测试集

如果要继续扩展，可以再加：

- `requirements.txt`
- `utils/`
- `outputs/`

---

## 11. 怎么运行测试

这个示例自带一个最小测试集，可以用标准库直接运行：

```bash
cd archive/CLI
python3 -m unittest discover -s tests
```

测试会检查：

- `--help` 是否能正常显示
- BMI 计算是否正确
- 缺少体重和身高时是否会提示补充信息
