# Label Studio 标注配置详解

Label Studio 使用 XML 标签语言定义标注界面，配置文件称为 **Labeling Config**。掌握 XML 配置是灵活使用 Label Studio 的核心技能。

## XML 配置基础结构

每个配置由 `<View>` 标签包裹，内部包含数据源标签和标注控件标签。数据源标签决定显示什么内容（图片、文本、音频），标注控件标签决定标注员如何标注。

```xml
<View>
  <!-- 数据源：显示图片 -->
  <Image name="img" value="$image" zoom="true"/>
  <!-- 标注控件：矩形框标签 -->
  <RectangleLabels name="tag" toName="img">
    <Label value="cat" background="#FF0000"/>
    <Label value="dog" background="#00FF00"/>
  </RectangleLabels>
</View>
```

关键属性说明：
- `name`：控件名称，导出数据时用于标识
- `toName`：关联的数据源名称（对应数据源标签的 `name` 属性）
- `value`：数据源字段名，`$image` 表示使用任务数据中的 `image` 字段

## 常用标注控件

### 图像目标检测（矩形框+标签）

```xml
<View>
  <Image name="img" value="$image" zoom="true"/>
  <RectangleLabels name="obj" toName="img">
    <Label value="car" background="red"/>
    <Label value="bus" background="blue"/>
    <Label value="truck" background="green"/>
  </RectangleLabels>
</View>
```

### 多边形标注（分割任务）

```xml
<View>
  <Image name="img" value="$image"/>
  <PolygonLabels name="seg" toName="img" strokeWidth="3">
    <Label value="road" background="rgba(128,128,128,0.3)"/>
    <Label value="building" background="rgba(255,0,0,0.3)"/>
  </PolygonLabels>
</View>
```

多边形标注使用鼠标逐点点击，双击完成闭合。适用于语义分割、实例分割任务。

### 关键点标注

```xml
<View>
  <Image name="img" value="$image"/>
  <KeyPointLabels name="kp" toName="img">
    <Label value="nose" background="red"/>
    <Label value="left_eye" background="blue"/>
    <Label value="right_eye" background="blue"/>
    <Label value="left_ear" background="green"/>
  </KeyPointLabels>
</View>
```

关键点标注每点击一次放置一个关键点，适用于人体姿态估计、面部关键点等任务。

### 椭圆标注（旋转框）

```xml
<View>
  <Image name="img" value="$image"/>
  <EllipseLabels name="ellipse" toName="img">
    <Label value="cell" background="purple"/>
  </EllipseLabels>
</View>
```

### 图像分类（单选/多选）

```xml
<View>
  <Image name="img" value="$image"/>
  <Choices name="quality" toName="img" choice="single-radio">
    <Choice value="clear" alias="清晰"/>
    <Choice value="blurry" alias="模糊"/>
    <Choice value="overexposed" alias="过曝"/>
  </Choices>
</View>
```

`choice="single-radio"` 为单选，`choice="multiple"` 为多选。

### 文本描述（自由输入）

```xml
<View>
  <Image name="img" value="$image"/>
  <TextArea name="description" toName="img"
    placeholder="请描述图片中的场景..."
    rows="3"/>
</View>
```

## 组合配置（多控件联动）

一个 View 中可以放置多个控件，实现复杂标注需求：

```xml
<View>
  <Image name="img" value="$image" zoom="true"/>

  <!-- 全局分类 -->
  <Choices name="scene" toName="img" choice="single-radio">
    <Choice value="daytime" alias="白天"/>
    <Choice value="night" alias="夜晚"/>
  </Choices>

  <!-- 目标检测 -->
  <RectangleLabels name="obj" toName="img">
    <Label value="car"/>
    <Label value="person"/>
  </RectangleLabels>

  <!-- 属性标注（选择框后设置属性） -->
  <Labels name="attr" toName="img">
    <Label value="occluded" alias="被遮挡"/>
    <Label value="truncated" alias="被截断"/>
  </Labels>
</View>
```

## 快捷键机制

Label Studio 自动为标签分配快捷键：`<Label>` 标签按顺序绑定数字键 1-9。例如配置了 car（1）、person（2）、bicycle（3），标注员按 1 选择"car"标签，然后直接在图片上画框。

## 高级配置技巧

- **`zoom="true"`**：启用图片缩放功能，适合标注小目标
- **`smart="true"`**：启用智能标注，AI 辅助自动贴合目标边缘
- **条件显示**：使用 `<View visibleWhen="...">` 根据前面选择动态显示控件
- **`required="true"`**：该控件必须填写才能提交

## 模板库

Label Studio 内置 30+ 配置模板，涵盖计算机视觉、自然语言处理、语音识别等领域。在 Settings → Labeling Interface → Browse Templates 中查看。

**参考：** https://labelstud.io/tags/
