import argparse
import asyncio
import yaml
import os
from src.main import main
import time

def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config

def convert_config_to_args(test_config: dict) -> tuple:
    """Convert YAML config to arguments format for src.main"""
    # Extract basic parameters
    input_path = test_config['input_path']
    output_path = test_config['output_path']
    scheme = test_config['scheme']
    tools = test_config.get('tools', [])
    
    # Convert models config to extra_args format
    extra_args = []
    
    # Handle temperature configuration
    # Get global temperature as default
    global_temperature = test_config.get('temperature', 0.0)
    
    if 'models' in test_config:
        models = test_config['models']
        if 'generator' in models:
            extra_args.extend(['--generator_model', models['generator']])
            # Handle generator temperature
            generator_temp = models.get('generator_temperature', global_temperature)
            extra_args.extend(['--generator_temperature', str(generator_temp)])
        if 'planner' in models:
            extra_args.extend(['--planner_model', models['planner']])
            # Handle planner temperature
            planner_temp = models.get('planner_temperature', global_temperature)
            extra_args.extend(['--planner_temperature', str(planner_temp)])
        if 'reviewer' in models:
            extra_args.extend(['--reviewer_model', models['reviewer']])
            # Handle reviewer temperature
            reviewer_temp = models.get('reviewer_temperature', global_temperature)
            extra_args.extend(['--reviewer_temperature', str(reviewer_temp)])
        if 'vision' in models:
            extra_args.extend(['--vision_model', models['vision']])
    
    # If no models section exists, still set default temperatures
    if 'models' not in test_config:
        extra_args.extend(['--generator_temperature', str(global_temperature)])
        extra_args.extend(['--planner_temperature', str(global_temperature)])
        extra_args.extend(['--reviewer_temperature', str(global_temperature)])
    
    # Convert advanced_reviewer_options config to extra_args format
    if 'advanced_reviewer_options' in test_config:
        advanced_reviewer_options = test_config['advanced_reviewer_options']
        if 'structured_preprocessing' in advanced_reviewer_options:
            extra_args.extend(['--structured_preprocessing', str(advanced_reviewer_options['structured_preprocessing'])])
        if 'preprocessing_only' in advanced_reviewer_options:
            extra_args.extend(['--preprocessing_only', str(advanced_reviewer_options['preprocessing_only'])])
        if 'refine_model' in advanced_reviewer_options:
            extra_args.extend(['--refine_model', str(advanced_reviewer_options['refine_model'])])
        if 'review_by_step' in advanced_reviewer_options:
            extra_args.extend(['--review_by_step', str(advanced_reviewer_options['review_by_step'])])
        if 'max_turn' in advanced_reviewer_options:
            extra_args.extend(['--max_turn', str(advanced_reviewer_options['max_turn'])])
        if 'voting_n' in advanced_reviewer_options:
            extra_args.extend(['--voting_n', str(advanced_reviewer_options['voting_n'])])

    # Convert single_llm_options config to extra_args format
    if 'single_llm_options' in test_config:
        single_llm_options = test_config['single_llm_options']
        if 'zero_shot_cot' in single_llm_options:
            extra_args.extend(['--zero_shot_cot', str(single_llm_options['zero_shot_cot'])])
        if 'cot' in single_llm_options:
            extra_args.extend(['--cot', str(single_llm_options['cot'])])
        if 'voting_n' in single_llm_options:
            extra_args.extend(['--voting_n', str(single_llm_options['voting_n'])])
        if 'structured_output' in single_llm_options:
            extra_args.extend(['--structured_output', str(single_llm_options['structured_output'])])
        if 'force_terminate' in single_llm_options:
            extra_args.extend(['--force_terminate', str(single_llm_options['force_terminate'])])

    # Convert loca_options config to extra_args format
    if 'loca_options' in test_config:
        loca_options = test_config['loca_options']
        if 'refine_model' in loca_options:
            extra_args.extend(['--refine_model', str(loca_options['refine_model'])])
        if 'max_error_times' in loca_options:
            extra_args.extend(['--max_error_times', str(loca_options['max_error_times'])])
        if 'target_times' in loca_options:
            extra_args.extend(['--target_times', str(loca_options['target_times'])])
        if 'ablation' in loca_options:
            extra_args.extend(['--ablation', str(loca_options['ablation'])])
        if 'keep_aug' in loca_options:
            extra_args.extend(['--keep_aug', str(loca_options['keep_aug'])])
        if 'keep_specific_verification' in loca_options:
            extra_args.extend(['--keep_specific_verification', str(loca_options['keep_specific_verification'])])
        if 'force_terminate' in loca_options:
            extra_args.extend(['--force_terminate', str(loca_options['force_terminate'])])
        if 'n_interpretation' in loca_options:
            extra_args.extend(['--n_interpretation', str(loca_options['n_interpretation'])])
        if 'stepwise_review' in loca_options:
            extra_args.extend(['--stepwise_review', str(loca_options['stepwise_review'])])
        if 'n_image_explanation' in loca_options:
            extra_args.extend(['--n_image_explanation', str(loca_options['n_image_explanation'])])
        if 'sub_problem' in loca_options:
            extra_args.extend(['--sub_problem', str(loca_options['sub_problem'])])

    # Convert vanilla_review_options config to extra_args format
    if 'vanilla_review_options' in test_config:
        vanilla_review_options = test_config['vanilla_review_options']
        if 'max_error_times' in vanilla_review_options:
            extra_args.extend(['--max_error_times', str(vanilla_review_options['max_error_times'])])
        if 'target_times' in vanilla_review_options:
            extra_args.extend(['--target_times', str(vanilla_review_options['target_times'])])

    # Add extra_params to extra_args
    if 'extra_params' in test_config:
        for key, value in test_config['extra_params'].items():
            extra_args.extend([f'--{key}', str(value)])
    
    return input_path, output_path, scheme, tools, extra_args

async def run_config(test_config: dict, config_name: str):
    """Run a single test configuration"""
    print(f"\n{'=' * 60}")
    print(f"Running configuration: {config_name}")
    print(f"{'=' * 60}")
    
    try:
        input_path, output_path, scheme, tools, extra_args = convert_config_to_args(test_config)
        
        # Create output directory if needed
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        print(f"Input: {input_path}")
        print(f"Output: {output_path}")
        print(f"Scheme: {scheme}")
        print(f"Tools: {tools}")
        if extra_args:
            print(f"Extra args: {extra_args}")
        
        # Run the main function
        await main(input_path, output_path, scheme, tools=tools, extra_args=extra_args)
        
        print(f"✓ Configuration '{config_name}' completed successfully")
        
    except Exception as e:
        print(f"✗ Configuration '{config_name}' failed: {str(e)}")
        raise

async def run_from_config(config_path: str = "config.yaml", config_names: list = None):
    """Run configurations from YAML file"""
    config = load_config(config_path)
    test_configs = config.get('test_configs', [])
    
    if not test_configs:
        print("No test configurations found in config file")
        return
    
    # Filter configurations if specific names provided
    if config_names:
        filtered_configs = []
        available_names = [cfg['name'] for cfg in test_configs]
        
        for name in config_names:
            found = False
            for cfg in test_configs:
                if cfg['name'] == name:
                    filtered_configs.append(cfg)
                    found = True
                    break
            if not found:
                print(f"Warning: Configuration '{name}' not found. Available: {available_names}")
        
        test_configs = filtered_configs
    
    if not test_configs:
        print("No valid configurations to run")
        return
    
    print(f"Found {len(test_configs)} configuration(s) to run")
    
    # Run configurations sequentially
    for test_config in test_configs:
        config_name = test_config['name']
        await run_config(test_config, config_name)

if __name__ == "__main__":
    # Print process id
    print(f"\nProcess ID: {os.getpid()}\n", flush=True)
    print(f"Starting the physics problem solver at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n",
          flush=True)
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='LOCA')
    
    # Add config-based arguments
    parser.add_argument('--config', default='config.yaml', help='Path to the configuration YAML file (default: config.yaml)')
    parser.add_argument('--config-name', nargs='*', help='Indicate specific configuration names to run')
    parser.add_argument('--list-configs', action='store_true', help='List available configurations and exit')
    
    args = parser.parse_args()
    
    try:
        # List configurations mode
        if args.list_configs:
            config = load_config(args.config)
            test_configs = config.get('test_configs', [])
            print(f"\nAvailable configurations in {args.config}:")
            for i, cfg in enumerate(test_configs, 1):
                print(f"  {i}. {cfg['name']} ({cfg['scheme']})")
            print()
            exit(0)
        asyncio.run(run_from_config(args.config, args.config_name))            
    except FileNotFoundError as e:
        print(f"Error: {e}")
        exit(1)
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
    
    print(f"Physics problem solver finished at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n",
          flush=True)
