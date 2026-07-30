---
name: annotation-guide
description: Comprehensive data annotation workflow guide covering labeling types, quality metrics, best practices, and common pitfalls. Use when the user asks about annotation techniques, labeling standards, quality evaluation, or wants to learn how to annotate data correctly.
---

# Data Annotation Guide

Comprehensive reference for data annotation — the process of labeling raw data (text, images, audio, video) to create training datasets for machine learning models.

## Annotation Types

### Text Annotation
| Type | Description | Example |
|------|-------------|---------|
| **Text Classification** | Assign a category label to a document or sentence | "This review is positive/negative/neutral" |
| **Named Entity Recognition (NER)** | Identify and classify named entities in text | [PER] Steve Jobs [/PER] founded [ORG] Apple [/ORG] |
| **Sentiment Analysis** | Determine emotional tone | "I love this product" → Positive |
| **Relation Extraction** | Identify relationships between entities | "Works at", "Located in" |
| **Part-of-Speech Tagging** | Label grammatical roles | Noun, Verb, Adjective |

### Image Annotation
| Type | Description | Key Metric |
|------|-------------|------------|
| **Bounding Box** | Draw rectangles around objects | IOU ≥ 0.5 |
| **Polygon Segmentation** | Trace object boundaries precisely | Pixel IOU |
| **Keypoint Annotation** | Mark specific points (joints, landmarks) | Point distance (OKS) |
| **Image Classification** | Assign a label to the entire image | Accuracy, F1 |
| **Semantic Segmentation** | Label every pixel with a class | mIOU |
| **Instance Segmentation** | Separate instances of the same class | mAP |

### Audio Annotation
| Type | Description |
|------|-------------|
| **Audio Classification** | Label audio clips by type (speech, music, noise) |
| **Speech Transcription** | Convert speech to text with timestamps |
| **Sound Event Detection** | Mark start/end times of specific sounds |
| **Speaker Diarization** | Identify "who spoke when" |

### Video Annotation
| Type | Description |
|------|-------------|
| **Object Tracking** | Follow objects across frames |
| **Action Recognition** | Label actions within time segments |
| **Frame Classification** | Label individual frames |
| **Event Detection** | Mark temporal boundaries of events |

## Quality Metrics

### Bounding Box: IOU (Intersection over Union)
```
IOU = Area of Overlap / Area of Union

IOU ≥ 0.5 → Generally considered a correct detection
IOU ≥ 0.7 → High-quality annotation
IOU < 0.3 → Needs significant improvement
```

### Classification: F1 Score
```
Precision = True Positives / (True Positives + False Positives)
Recall = True Positives / (True Positives + False Negatives)
F1 = 2 × (Precision × Recall) / (Precision + Recall)

Precision measures: "When I say it's X, how often am I right?"
Recall measures: "Of all the actual X, how many did I find?"
F1 measures: Balanced performance
```

### Inter-Annotator Agreement
| Metric | Use Case |
|--------|----------|
| **Cohen's Kappa** | Two annotators, categorical labels |
| **Fleiss' Kappa** | Multiple annotators, categorical labels |
| **Krippendorff's Alpha** | Any number of annotators, any data type |
| **IOU Agreement** | Bounding box/polygon overlap between annotators |

Thresholds:
- Kappa > 0.8 → Excellent agreement
- Kappa 0.6-0.8 → Good agreement
- Kappa < 0.4 → Poor agreement — guidelines need revision

## Best Practices

### Guideline Design
1. **Be specific**: "Label only vehicles visible in the front windshield" not "Label cars"
2. **Include edge cases**: What defines "occluded"? When is a partial object still labelable?
3. **Use visual examples**: Show correct AND incorrect annotations
4. **Define label priority**: When multiple labels could apply, which takes precedence?

### Annotation Workflow
1. **Pilot batch**: Annotate 100 samples, review disagreements, refine guidelines
2. **Consistency check**: Calculate inter-annotator agreement after every batch
3. **Edge case log**: Document ambiguous cases and resolutions
4. **Regular recalibration**: Re-annotate a gold standard set periodically

### Common Pitfalls
| Pitfall | Solution |
|---------|----------|
| **Label inconsistency** | Regular calibration meetings, clear guidelines with examples |
| **Boundary ambiguity** | Define explicit rules (e.g., "bounding box includes the tail") |
| **Annotation fatigue** | Limit sessions to 45-60 minutes, rotate task types |
| **Class imbalance** | Over-sample rare classes in review, use stratified sampling |
| **Confirmation bias** | Rotate annotators across different data sources |
| **Guideline drift** | Lock guidelines after pilot phase, version-control all changes |

## When to Use the annotation_check Tool

Call `annotation_check` when:
- The user has completed an annotation task and wants evaluation
- You need to compute precision, recall, F1, or IOU for bounding boxes
- You want to provide quantitative feedback on annotation quality

The tool accepts:
- `predictions`: JSON array of annotated boxes/labels
- `ground_truth`: JSON array of correct boxes/labels  
- `task_type`: "bbox" or "classification"
