import sys
import os
import subprocess
import time
import json
from pathlib import Path


MOTORAI_ROOT = Path(__file__).resolve().parents[2]
if str(MOTORAI_ROOT) not in sys.path:
    sys.path.insert(0, str(MOTORAI_ROOT))

from motorai_config import load_settings, normalize_optimize_config


def load_json_object(path):
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def bat_has_assignment(path, name, value):
    try:
        text = Path(path).read_text(encoding='utf-8-sig')
    except OSError:
        return False
    return f'set "{name}={value}"' in text


def vcxproj_has_current_gmp_root(sln_path, gmp_root):
    sln_dir = Path(sln_path).parent
    vcxproj_files = sorted(sln_dir.glob('*.vcxproj'))
    if not vcxproj_files:
        return False

    inspected = False
    for vcxproj_path in vcxproj_files:
        try:
            text = vcxproj_path.read_text(encoding='utf-8-sig')
        except OSError:
            return False

        if 'GMPCorePropertySheet.props' not in text and 'GMPSrcGenPropertySheet.props' not in text:
            continue

        inspected = True
        if f'<GMP_PRO_LOCATION>{gmp_root}</GMP_PRO_LOCATION>' not in text:
            return False
        if '..\\..\\..\\..\\..\\csp\\windows_simulink\\GMPCorePropertySheet.props' in text:
            return False
        if '..\\..\\..\\..\\..\\tools\\facilities_generator\\GMPSrcGenPropertySheet.props' in text:
            return False
        if r'Project="$(GMP_PRO_LOCATION)\csp\windows_simulink\GMPCorePropertySheet.props"' not in text:
            return False
        if r'Project="$(GMP_PRO_LOCATION)\tools\facilities_generator\GMPSrcGenPropertySheet.props"' not in text:
            return False

    return inspected


def normalize_path_text(value):
    value = str(value or '').strip()
    if not value:
        return ''
    try:
        return str(Path(value).expanduser().resolve())
    except OSError:
        return str(Path(value).expanduser())


def optimize_project_is_current(project_json_path, optimize_config):
    project = load_json_object(project_json_path)
    if not project:
        return False

    src_folder_path = normalize_path_text(project.get('src_folder_path', ''))
    simulink_model_path = normalize_path_text(project.get('simulink_model_path', ''))
    sln_path = normalize_path_text(project.get('sln_path', ''))
    parameter_header_path = normalize_path_text(
        project.get('iteration_parameter_header_path')
        or project.get('parameter_header_path')
        or (Path(src_folder_path) / 'paras.generated.h' if src_folder_path else '')
    )
    if not src_folder_path or not simulink_model_path or not sln_path:
        return False

    sln_dir = str(Path(sln_path).parent)
    gmp_root = normalize_path_text(project.get('gmp_path', ''))
    if not gmp_root:
        for candidate in (Path(sln_dir), *Path(sln_dir).parents):
            if candidate.name.lower() == 'ctl':
                gmp_root = normalize_path_text(candidate.parent)
                break

    optimize_root = Path(optimize_config['root'])
    agent_project_path = Path(optimize_config['agent_project'])
    build_sln_path = optimize_root / 'agent_optimize' / 'build_sln.bat'
    start_exe_path = optimize_root / 'agent_optimize' / 'start_exe.bat'
    run_local_quick_path = optimize_root / 'agent_silhelper' / 'run_local_quick.bat'

    agent_project = load_json_object(agent_project_path)
    resources = agent_project.get('resources') if isinstance(agent_project.get('resources'), dict) else {}
    automation = agent_project.get('automation') if isinstance(agent_project.get('automation'), dict) else {}
    project_src = resources.get('project_src') if isinstance(resources.get('project_src'), dict) else {}

    if normalize_path_text(project_src.get('path', '')) != src_folder_path:
        return False
    if normalize_path_text(automation.get('sim_model_path', '')) != simulink_model_path:
        return False
    if normalize_path_text(automation.get('parameter_header', '')) != parameter_header_path:
        return False

    if gmp_root and not bat_has_assignment(build_sln_path, 'REPO_ROOT', gmp_root):
        return False
    if gmp_root and not bat_has_assignment(build_sln_path, 'GMP_PRO_LOCATION', gmp_root):
        return False
    if not bat_has_assignment(build_sln_path, 'SLN_PATH', sln_path):
        return False
    if not bat_has_assignment(build_sln_path, 'SLN_DIR', sln_dir):
        return False
    if not bat_has_assignment(start_exe_path, 'SLN_DIR', sln_dir):
        return False
    if not bat_has_assignment(run_local_quick_path, 'DEFAULT_MODEL_PATH', simulink_model_path):
        return False
    if gmp_root and not vcxproj_has_current_gmp_root(sln_path, gmp_root):
        return False

    return True


def run_agent_optimization(project_json_path):
    optimize_config = normalize_optimize_config(load_settings())
    
    if not os.path.exists(project_json_path):
        print(f"错误：项目文件不存在: {project_json_path}")
        return 1
    
    project_json_path = os.path.abspath(project_json_path)
    
    config_project_script = optimize_config['config_project']
    run_tuning_bat = optimize_config['run_tuning_agent']
    
    if not os.path.exists(config_project_script):
        print(f"错误：config_project.py 不存在: {config_project_script}")
        return 1
    
    if not os.path.exists(run_tuning_bat):
        print(f"错误：run_tuning_agent.bat 不存在: {run_tuning_bat}")
        return 1
    
    if optimize_project_is_current(project_json_path, optimize_config):
        print("Optimize 项目路径已是当前项目，跳过配置脚本。")
    else:
        print(f"开始执行配置项目脚本...")
        print(f"项目文件: {project_json_path}")

        try:
            result = subprocess.run(
                [sys.executable, config_project_script, project_json_path],
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
            print(f"config_project.py 执行成功")
            if result.stdout:
                print(f"输出: {result.stdout}")
        except subprocess.CalledProcessError as e:
            print(f"config_project.py 执行失败: {e.stderr or e.stdout}")
            return 1

        print("等待 2 秒后启动调优脚本...")
        time.sleep(2)

    print(f"\n开始执行调优脚本...")
    
    try:
        cmd_command = f'start cmd /k "{run_tuning_bat} \"{project_json_path}\""'
        subprocess.run(cmd_command, shell=True, check=True, cwd=os.path.dirname(run_tuning_bat))
        print(f"run_tuning_agent.bat 已在新窗口启动")
    except subprocess.CalledProcessError as e:
        print(f"启动 run_tuning_agent.bat 失败: {e}")
        return 1
    
    print("\n所有操作完成！")
    return 0

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法：python run_agent.py <项目JSON文件路径>")
        sys.exit(1)
    
    project_json_path = sys.argv[1]
    exit_code = run_agent_optimization(project_json_path)
    sys.exit(exit_code)
