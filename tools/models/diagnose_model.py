#!/usr/bin/env python3
"""Diagnostic script to understand model behavior."""

import json
from pathlib import Path
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import numpy as np


def diagnose_model(model_path, dataset_path, num_samples=100):
    """Analyze model predictions and confidence."""
    
    print("="*70)
    print("MODEL DIAGNOSIS")
    print("="*70)
    
    # Load model
    print(f"\n1. Loading model from {model_path}...")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    model.eval()
    
    # Load label map
    label_map_path = Path(model_path) / "label_map.json"
    with open(label_map_path) as f:
        label2id = json.load(f)
    id2label = {v: k for k, v in label2id.items()}
    
    print(f"   Model has {len(id2label)} categories")
    
    # Load some examples
    print(f"\n2. Loading {num_samples} examples from {dataset_path}...")
    examples = []
    with open(dataset_path) as f:
        for i, line in enumerate(f):
            if i >= num_samples:
                break
            data = json.loads(line)
            examples.append({
                'text': data['text'],
                'true_label': data['dct_label']
            })
    
    print(f"   Loaded {len(examples)} examples")
    
    # Test predictions
    print(f"\n3. Testing predictions...")
    confidences = []
    correct = 0
    total = 0
    
    predictions_by_confidence = {
        'very_high': [],  # >0.95
        'high': [],       # 0.80-0.95
        'medium': [],     # 0.60-0.80
        'low': []         # <0.60
    }
    
    for ex in examples:
        inputs = tokenizer(ex['text'], return_tensors="pt", truncation=True, max_length=256)
        
        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)
            confidence, pred_id = probs.max(dim=-1)
        
        pred_label = id2label[pred_id.item()]
        conf = confidence.item()
        confidences.append(conf)
        
        is_correct = pred_label == ex['true_label']
        if is_correct:
            correct += 1
        total += 1
        
        # Categorize by confidence
        sample = {
            'text': ex['text'][:50] + '...' if len(ex['text']) > 50 else ex['text'],
            'predicted': pred_label,
            'true': ex['true_label'],
            'confidence': conf,
            'correct': is_correct
        }
        
        if conf > 0.95:
            predictions_by_confidence['very_high'].append(sample)
        elif conf > 0.80:
            predictions_by_confidence['high'].append(sample)
        elif conf > 0.60:
            predictions_by_confidence['medium'].append(sample)
        else:
            predictions_by_confidence['low'].append(sample)
    
    # Print statistics
    print(f"\n" + "="*70)
    print("RESULTS")
    print("="*70)
    
    print(f"\n📊 Confidence Distribution:")
    print(f"   Min confidence:    {min(confidences):.4f}")
    print(f"   Max confidence:    {max(confidences):.4f}")
    print(f"   Mean confidence:   {np.mean(confidences):.4f}")
    print(f"   Median confidence: {np.median(confidences):.4f}")
    
    print(f"\n📊 Confidence Buckets:")
    print(f"   Very High (>0.95): {len(predictions_by_confidence['very_high'])} examples ({100*len(predictions_by_confidence['very_high'])/total:.1f}%)")
    print(f"   High (0.80-0.95):  {len(predictions_by_confidence['high'])} examples ({100*len(predictions_by_confidence['high'])/total:.1f}%)")
    print(f"   Medium (0.60-0.80): {len(predictions_by_confidence['medium'])} examples ({100*len(predictions_by_confidence['medium'])/total:.1f}%)")
    print(f"   Low (<0.60):       {len(predictions_by_confidence['low'])} examples ({100*len(predictions_by_confidence['low'])/total:.1f}%)")
    
    print(f"\n📊 Overall Accuracy on Sample: {100*correct/total:.1f}%")
    
    # Show examples from each bucket
    print(f"\n" + "="*70)
    print("EXAMPLE PREDICTIONS")
    print("="*70)
    
    for bucket_name, bucket_samples in predictions_by_confidence.items():
        if bucket_samples:
            print(f"\n🔹 {bucket_name.upper()} CONFIDENCE:")
            for i, sample in enumerate(bucket_samples[:3], 1):  # Show first 3
                status = "✓" if sample['correct'] else "✗"
                print(f"   {i}. {status} Text: {sample['text']}")
                print(f"      Predicted: {sample['predicted']} | True: {sample['true']} | Conf: {sample['confidence']:.3f}")
    
    # Diagnosis
    print(f"\n" + "="*70)
    print("DIAGNOSIS")
    print("="*70)
    
    mean_conf = np.mean(confidences)
    very_high_pct = 100 * len(predictions_by_confidence['very_high']) / total
    
    if mean_conf < 0.70:
        print("\n⚠️  PROBLEM: Model has LOW average confidence")
        print("   → The model is very uncertain about most predictions")
        print("   → This explains why evaluation coverage is low (4.6%)")
        print("\n💡 SOLUTION: Retrain with better settings:")
        print("   → Use --epochs 3 instead of 1")
        print("   → Use --batch-size 8 instead of 2")
        print("   → This will give the model more time to learn properly")
    elif very_high_pct < 20:
        print("\n⚠️  PROBLEM: Very few high-confidence predictions")
        print("   → Model needs more training")
        print("\n💡 SOLUTION: Retrain with --epochs 3 and --batch-size 8")
    else:
        print("\n✅ Model confidence looks reasonable!")
        print("   The evaluation threshold tuning might be too aggressive")


if __name__ == "__main__":
    MODEL_PATH = "models/tmp_classifier"
    DATASET_PATH = "datasets/sample_block_dataset.jsonl"
    
    print("\n🔬 Running diagnostics on your model...\n")
    
    try:
        diagnose_model(MODEL_PATH, DATASET_PATH)
        print("\n" + "="*70)
        print("NEXT STEPS")
        print("="*70)
        print("\nBased on the diagnosis above, you should:")
        print("1. Look at the mean confidence score")
        print("2. If it's low (<0.70), retrain with better settings")
        print("3. Use: --epochs 3 --batch-size 8")
        print("\n")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
