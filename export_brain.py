#!/usr/bin/env python3
import os
import shutil

def export_brain_context():
    source_brain = "/Users/harshaabhinavkusampudi/.gemini/antigravity/brain"
    target_dir = "/Users/harshaabhinavkusampudi/Downloads/Tesserae-V6-Local-Setup/antigravity_context"
    
    # Tesserae V6 related conversation IDs
    conversations = [
        "210d9c2c-18ca-4c73-a5f6-f18d8b261c44", # Current
        "bef220e4-b1c2-4695-9049-eb93f8f5ecfb",
        "9cb0eff7-cad6-4346-8ee9-6e18acd40452",
        "dc963d3d-331a-41eb-b7ec-39b1a5b680f3",
        "bf74b443-7acd-4d6c-9add-cb2afb1d3912",
        "7b10ca59-224d-440a-becb-ea7b82f51f88"
    ]
    
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        
    for conv_id in conversations:
        conv_source = os.path.join(source_brain, conv_id)
        if not os.path.exists(conv_source):
            continue
            
        conv_target = os.path.join(target_dir, conv_id)
        if not os.path.exists(conv_target):
            os.makedirs(conv_target)
            
        # Copy logs
        log_source = os.path.join(conv_source, ".system_generated", "logs", "overview.txt")
        if os.path.exists(log_source):
            target_log_dir = os.path.join(conv_target, "logs")
            os.makedirs(target_log_dir, exist_ok=True)
            shutil.copy2(log_source, os.path.join(target_log_dir, "overview.txt"))
            
        # Copy artifacts
        artifacts_source = os.path.join(conv_source, "artifacts")
        if os.path.exists(artifacts_source):
            target_artifacts_dir = os.path.join(conv_target, "artifacts")
            if os.path.exists(target_artifacts_dir):
                shutil.rmtree(target_artifacts_dir)
            shutil.copytree(artifacts_source, target_artifacts_dir)

    print(f"Exported {len(conversations)} conversations to {target_dir}")

if __name__ == '__main__':
    export_brain_context()
