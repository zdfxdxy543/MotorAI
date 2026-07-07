import json
import sys
import shutil
from pathlib import Path
from typing import Dict, Any


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load JSON file from given path."""
    if not file_path.exists():
        raise FileNotFoundError(f"JSON file not found: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in file: {file_path}\n{e}") from e


def save_json_file(file_path: Path, data: Dict[str, Any]) -> None:
    """Save JSON data to file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def modify_agent_project_json(agent_project_path: Path, src_folder_path: str, simulink_model_path: str) -> None:
    """Modify agent_project.json with new paths."""
    data = load_json_file(agent_project_path)
    
    # 修改 resources -> project_src -> path
    if 'resources' in data and 'project_src' in data['resources']:
        data['resources']['project_src']['path'] = src_folder_path
        print(f"Updated agent_project.json: resources.project_src.path = {src_folder_path}")
    else:
        print("Warning: resources.project_src not found in agent_project.json")
    
    # 修改 automation -> sim_model_path
    if 'automation' in data:
        data['automation']['sim_model_path'] = simulink_model_path
        print(f"Updated agent_project.json: automation.sim_model_path = {simulink_model_path}")
    else:
        print("Warning: automation not found in agent_project.json")
    
    save_json_file(agent_project_path, data)


def modify_build_sln_bat(bat_path: Path, sln_dir: str) -> None:
    """Modify build_sln.bat with new SLN path."""
    with open(bat_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 第28行: set "SLN_PATH=<sln_path>\GMP_Motor_Control_simulink.sln"
    sln_path_full = f'{sln_dir}\\GMP_Motor_Control_simulink.sln'
    lines[27] = f'set "SLN_PATH={sln_path_full}"\n'  # 索引从0开始
    
    # 第29行: set "SLN_DIR=<sln_path>"
    lines[28] = f'set "SLN_DIR={sln_dir}"\n'
    
    # 第113行: if exist "<sln_path>\GMP_Motor_Control_simulink.sln" (
    lines[112] = f'    if exist "{sln_path_full}" (\n'
    
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"Updated build_sln.bat with SLN_DIR = {sln_dir}")


def modify_run_local_quick_bat(bat_path: Path, sln_dir: str) -> None:
    """Modify run_local_quick.bat with new model path."""
    with open(bat_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 第14行: set "DEFAULT_MODEL_PATH=<sln_path>\MCS_STD_PMSM_MODEL_2022b.slx"
    model_path = f'{sln_dir}\\MCS_STD_PMSM_MODEL.slx'
    lines[13] = f'set "DEFAULT_MODEL_PATH={model_path}"\n'  # 索引从0开始
    
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"Updated run_local_quick.bat with DEFAULT_MODEL_PATH = {model_path}")


def modify_start_exe_bat(bat_path: Path, sln_dir: str) -> None:
    """Modify start_exe.bat with new SLN directory."""
    with open(bat_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 第31行: set "SLN_DIR=<sln_dir>"
    lines[30] = f'set "SLN_DIR={sln_dir}"\n'  # 索引从0开始
    
    # 第82行: if exist "%CURRENT%\ctl\suite\mcs_pmsm_nt\project\simulate\GMP_Motor_Control_simulink.sln" (
    # 需要提取相对于 repo_root 的路径部分 (ctl\suite\xxx\project\simulate\GMP_Motor_Control_simulink.sln)
    # 从 sln_dir 中提取相对路径
    relative_path = sln_dir
    if '\\ctl\\' in relative_path:
        relative_path = relative_path[relative_path.index('\\ctl\\') + 1:]  # 去掉前面的反斜杠
    sln_relative_path = f'{relative_path}\\GMP_Motor_Control_simulink.sln'
    lines[81] = f'    if exist "%CURRENT%\\{sln_relative_path}" (\n'
    
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"Updated start_exe.bat with SLN_DIR = {sln_dir}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python config_project.py <path_to_config.json>")
        print("Example: python config_project.py E:\\Related_Github_Project\\gmp_pro\\ctl\\suite\\Main1\\Main1.json")
        sys.exit(1)
    
    # 获取传入的 JSON 文件路径
    config_json_path = Path(sys.argv[1])
    
    if not config_json_path.exists():
        print(f"Error: JSON file not found: {config_json_path}")
        sys.exit(1)
    
    # 加载配置
    config = load_json_file(config_json_path)
    
    # 提取必需的键
    required_keys = ['sln_path', 'simulink_model_path', 'src_folder_path']
    missing_keys = [k for k in required_keys if k not in config]
    if missing_keys:
        print(f"Error: Missing required keys in JSON: {', '.join(missing_keys)}")
        sys.exit(1)
    
    sln_path = config['sln_path']
    simulink_model_path = config['simulink_model_path']
    src_folder_path = config['src_folder_path']
    
    # 从 sln_path 提取文件夹路径（去掉文件名）
    sln_dir = str(Path(sln_path).parent)
    
    print(f"Loaded configuration:")
    print(f"  sln_path: {sln_path}")
    print(f"  sln_dir: {sln_dir}")
    print(f"  simulink_model_path: {simulink_model_path}")
    print(f"  src_folder_path: {src_folder_path}")
    print()
    
    # 计算目标文件路径（相对于本脚本的位置）
    script_dir = Path(__file__).resolve().parent
    agent_optimize_dir = script_dir / 'agent_optimize'
    example_dir = agent_optimize_dir / 'Example'
    
    agent_project_path = agent_optimize_dir / 'agent_project.json'
    build_sln_path = agent_optimize_dir / 'build_sln.bat'
    run_local_quick_path = script_dir / 'agent_silhelper' / 'run_local_quick.bat'
    start_exe_path = agent_optimize_dir / 'start_exe.bat'
    
    # 执行修改
    try:
        # 从 Example 文件夹复制模板文件到 agent_optimize 文件夹覆盖
        print("Copying template files from Example folder...")
        shutil.copy2(example_dir / 'agent_project.json', agent_project_path)
        shutil.copy2(example_dir / 'build_sln.bat', build_sln_path)
        shutil.copy2(example_dir / 'start_exe.bat', start_exe_path)
        print("Copied template files successfully")
        print()
        
        modify_agent_project_json(agent_project_path, src_folder_path, simulink_model_path)
        modify_build_sln_bat(build_sln_path, sln_dir)
        modify_run_local_quick_bat(run_local_quick_path, sln_dir)
        modify_start_exe_bat(start_exe_path, sln_dir)
        print()
        print("Successfully updated all configuration files!")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
