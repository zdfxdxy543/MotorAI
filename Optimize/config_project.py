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


def derive_gmp_root_from_sln_dir(sln_dir: str) -> str:
    """Derive the GMP repository root from .../ctl/suite/<project>/project/simulate."""
    path = Path(sln_dir).expanduser().resolve()

    for candidate in (path, *path.parents):
        facilities_bat = candidate / 'tools' / 'facilities_generator' / 'gmp_fac_generate_srcs_example.bat'
        if facilities_bat.exists():
            return str(candidate)

    for candidate in (path, *path.parents):
        if candidate.name.lower() == 'ctl':
            return str(candidate.parent)

    raise ValueError(f"Unable to derive GMP root from sln_dir: {sln_dir}")


def resolve_gmp_root(config: Dict[str, Any], sln_dir: str) -> str:
    """Resolve GMP root from project JSON first, then fall back to sln_dir."""
    configured_root = str(config.get('gmp_path') or config.get('gmp_root') or '').strip()
    if configured_root:
        root = Path(configured_root).expanduser().resolve()
        facilities_bat = root / 'tools' / 'facilities_generator' / 'gmp_fac_generate_srcs_example.bat'
        if not facilities_bat.exists():
            raise FileNotFoundError(
                f"Configured gmp_path is not a valid GMP root: {root}\n"
                f"Missing: {facilities_bat}"
            )
        return str(root)

    return derive_gmp_root_from_sln_dir(sln_dir)


def rewrite_bat_variables(bat_path: Path, replacements: Dict[str, str], *, repo_root: str | None = None) -> None:
    """Rewrite set "NAME=value" assignments without relying on fixed line numbers."""
    with open(bat_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    normalized_replacements = {key.upper(): value for key, value in replacements.items()}
    rewritten = []
    skip_next_repo_error_check = False
    replaced_keys = set()

    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()

        if repo_root is not None and lowered.startswith('call :find_repo_root'):
            rewritten.append(f'set "REPO_ROOT={repo_root}"\n')
            skip_next_repo_error_check = True
            continue

        if skip_next_repo_error_check and lowered == 'if errorlevel 1 goto err_repo_root':
            skip_next_repo_error_check = False
            continue
        skip_next_repo_error_check = False

        replaced = False
        for key, value in normalized_replacements.items():
            if lowered.startswith(f'set "{key.lower()}='):
                rewritten.append(f'set "{key}={value}"\n')
                replaced_keys.add(key)
                replaced = True
                break
        if not replaced:
            rewritten.append(line)

    missing = sorted(set(normalized_replacements) - replaced_keys)
    if missing:
        raise ValueError(f"{bat_path} missing expected variable assignment(s): {', '.join(missing)}")

    with open(bat_path, 'w', encoding='utf-8') as f:
        f.writelines(rewritten)


def modify_agent_project_json(
    agent_project_path: Path,
    src_folder_path: str,
    simulink_model_path: str,
    parameter_header_path: str,
) -> None:
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
        data['automation']['parameter_header'] = parameter_header_path
        print(f"Updated agent_project.json: automation.sim_model_path = {simulink_model_path}")
        print(f"Updated agent_project.json: automation.parameter_header = {parameter_header_path}")
    else:
        print("Warning: automation not found in agent_project.json")
    
    save_json_file(agent_project_path, data)


def modify_build_sln_bat(bat_path: Path, sln_dir: str, gmp_root: str) -> None:
    """Modify build_sln.bat with new SLN path."""
    sln_path_full = f'{sln_dir}\\GMP_Motor_Control_simulink.sln'
    rewrite_bat_variables(
        bat_path,
        {
            'SLN_PATH': sln_path_full,
            'SLN_DIR': sln_dir,
            'LOG_DIR': '%SCRIPT_DIR%..\\log\\build',
        },
        repo_root=gmp_root,
    )

    print(f"Updated build_sln.bat with REPO_ROOT = {gmp_root}")
    print(f"Updated build_sln.bat with SLN_DIR = {sln_dir}")


def modify_run_local_quick_bat(bat_path: Path, sln_dir: str) -> None:
    """Modify run_local_quick.bat with new model path."""
    model_path = f'{sln_dir}\\MCS_STD_PMSM_MODEL.slx'
    rewrite_bat_variables(
        bat_path,
        {
            'DEFAULT_MODEL_PATH': model_path,
        },
    )

    print(f"Updated run_local_quick.bat with DEFAULT_MODEL_PATH = {model_path}")


def modify_start_exe_bat(bat_path: Path, sln_dir: str, gmp_root: str) -> None:
    """Modify start_exe.bat with new SLN directory."""
    rewrite_bat_variables(
        bat_path,
        {
            'SLN_DIR': sln_dir,
            'LOG_DIR': '%SCRIPT_DIR%..\\log\\build',
        },
        repo_root=gmp_root,
    )

    print(f"Updated start_exe.bat with REPO_ROOT = {gmp_root}")
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
    parameter_header_path = (
        config.get('iteration_parameter_header_path')
        or config.get('parameter_header_path')
        or str(Path(src_folder_path) / 'paras.generated.h')
    )
    
    # 从 sln_path 提取文件夹路径（去掉文件名）
    sln_dir = str(Path(sln_path).parent)
    gmp_root = resolve_gmp_root(config, sln_dir)
    
    print(f"Loaded configuration:")
    print(f"  gmp_root: {gmp_root}")
    print(f"  sln_path: {sln_path}")
    print(f"  sln_dir: {sln_dir}")
    print(f"  simulink_model_path: {simulink_model_path}")
    print(f"  src_folder_path: {src_folder_path}")
    print(f"  parameter_header_path: {parameter_header_path}")
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
        
        modify_agent_project_json(agent_project_path, src_folder_path, simulink_model_path, parameter_header_path)
        modify_build_sln_bat(build_sln_path, sln_dir, gmp_root)
        modify_run_local_quick_bat(run_local_quick_path, sln_dir)
        modify_start_exe_bat(start_exe_path, sln_dir, gmp_root)
        print()
        print("Successfully updated all configuration files!")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
