import os
import sys
import json
import shutil
import subprocess

def find_llmfit():
    binary_name = "llmfit.exe" if sys.platform == "win32" else "llmfit"
    
    # Check if it's in the current directory
    if os.path.exists(binary_name):
        print(f"✅ Found {binary_name} in current directory.")
        return f".\\{binary_name}" if sys.platform == "win32" else f"./{binary_name}"
        
    # Check if it's in the system PATH
    path_to_llmfit = shutil.which("llmfit")
    if path_to_llmfit:
         print(f"✅ Found llmfit in PATH: {path_to_llmfit}")
         return path_to_llmfit
         
    print(f"❌ Could not find llmfit. Please ensure it is installed (e.g., via 'cargo install llmfit').")
    sys.exit(1)

def run_llmfit_recommend(binary_path):
    print("🔍 Running llmfit to detect hardware and recommend models...")
    try:
        cmd = [binary_path, "recommend", "--json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ llmfit failed: {e.stderr}")
        sys.exit(1)
    except json.JSONDecodeError as e:
         print(f"❌ Failed to parse llmfit JSON output: {e}\nOutput was: {result.stdout}")
         sys.exit(1)

def update_opencode_json(recommendations):
    opencode_path = "opencode.json"
    print(f"📝 Updating {opencode_path}...")
    
    if not os.path.exists(opencode_path):
        print(f"❌ {opencode_path} not found.")
        sys.exit(1)
        
    with open(opencode_path, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    if "provider" not in config or "vllm" not in config["provider"]:
         print(f"❌ Invalid {opencode_path} format. Missing provider.vllm")
         sys.exit(1)
         
    if "models" not in config["provider"]["vllm"]:
        config["provider"]["vllm"]["models"] = {}
        
    updated_count = 0
    best_model = None

    for model in recommendations.get("models", []):
         if not best_model:
              best_model = model["name"] # The first one is the top recommendation
              
         model_id = model["name"]
         # Map context window and max tokens based on llmfit output if available
         context_window = model.get("context_length", 32768)
         # maxTokens is often a fraction of context window, cap at a reasonable size
         max_tokens = min(8192, context_window // 4) 
         
         if model_id not in config["provider"]["vllm"]["models"]:
             config["provider"]["vllm"]["models"][model_id] = {
                 "name": f"{model_id.split('/')[-1]} (vLLM, {model.get('best_quant', 'auto')})",
                 "contextWindow": context_window,
                 "maxTokens": max_tokens
             }
             updated_count += 1
             print(f"  ➕ Added {model_id} to opencode.json")
             
    with open(opencode_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        
    if updated_count > 0:
        print(f"✅ Successfully added {updated_count} models to {opencode_path}.")
    else:
        print(f"ℹ️ {opencode_path} is already up-to-date with llmfit recommendations.")
        
    return best_model

def update_run_sh(best_model):
    if not best_model:
        return
        
    run_sh_path = "run.sh"
    print(f"📝 Updating {run_sh_path} with best model: {best_model}...")
    
    if not os.path.exists(run_sh_path):
        print(f"❌ {run_sh_path} not found.")
        return
        
    with open(run_sh_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    updated = False
    for i, line in enumerate(lines):
        if "--model " in line:
            # Preserve leading whitespace
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = f"{indent}--model {best_model} \\\n"
            updated = True
            break
            
    if updated:
         with open(run_sh_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
         print(f"✅ Successfully set default model to {best_model} in {run_sh_path}.")
    else:
         print(f"❌ Could not find '--model' flag in {run_sh_path} to update.")

def main():
    print("🚀 Starting auto-configuration process...")
    binary_path = find_llmfit()
    recommendations = run_llmfit_recommend(binary_path)
    best_model = update_opencode_json(recommendations)
    # Disabled automatic run.sh update to preserve our fine-tuned AWQ configuration
    # update_run_sh(best_model)
    print("🎉 Auto-configuration complete!")

if __name__ == "__main__":
    main()
