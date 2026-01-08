#!/usr/bin/env python3
"""
Validation script for Amazon Ads Data Sync implementation

This script validates:
1. All new files are syntactically correct
2. New methods exist in amazon_client
3. Data sync module structure is correct
4. Main.py routing logic is correct
"""
import sys
import ast
from pathlib import Path

def validate_python_syntax(file_path: Path) -> bool:
    """Validate Python file syntax"""
    try:
        with open(file_path, 'r') as f:
            ast.parse(f.read())
        print(f"✅ {file_path.name}: Syntax valid")
        return True
    except SyntaxError as e:
        print(f"❌ {file_path.name}: Syntax error - {e}")
        return False

def validate_methods_exist(file_path: Path, methods: list) -> bool:
    """Check if methods exist in a Python file"""
    try:
        with open(file_path, 'r') as f:
            tree = ast.parse(f.read())
        
        found_methods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                found_methods.add(node.name)
        
        missing = set(methods) - found_methods
        if missing:
            print(f"❌ {file_path.name}: Missing methods: {missing}")
            return False
        else:
            print(f"✅ {file_path.name}: All required methods found")
            return True
    except Exception as e:
        print(f"❌ {file_path.name}: Error checking methods - {e}")
        return False

def validate_imports(file_path: Path, expected_imports: list) -> bool:
    """Check if file has expected imports"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        missing = []
        for imp in expected_imports:
            if imp not in content:
                missing.append(imp)
        
        if missing:
            print(f"⚠️  {file_path.name}: Missing imports: {missing}")
            return False
        else:
            print(f"✅ {file_path.name}: All expected imports found")
            return True
    except Exception as e:
        print(f"❌ {file_path.name}: Error checking imports - {e}")
        return False

def main():
    base_path = Path(__file__).parent.parent
    
    print("=" * 60)
    print("🔍 Validating Amazon Ads Data Sync Implementation")
    print("=" * 60)
    print()
    
    all_valid = True
    
    # 1. Validate amazon_client.py
    print("1️⃣  Validating amazon_client.py...")
    amazon_client_path = base_path / "backend/shared/amazon_client.py"
    
    all_valid &= validate_python_syntax(amazon_client_path)
    all_valid &= validate_methods_exist(amazon_client_path, [
        'create_report',
        'get_report_status', 
        'download_report',
        'get_campaigns_report',
        'get_keywords_report',
        'get_search_terms_report'
    ])
    print()
    
    # 2. Validate data sync job
    print("2️⃣  Validating amazon_ads_sync.py...")
    sync_job_path = base_path / "backend/jobs/data_sync/amazon_ads_sync.py"
    
    all_valid &= validate_python_syntax(sync_job_path)
    all_valid &= validate_methods_exist(sync_job_path, [
        'sync_campaigns',
        'sync_keywords',
        'sync_campaign_performance',
        'sync_keyword_performance',
        'sync_advertised_products',
        'run_full_sync',
        'run_data_sync'
    ])
    all_valid &= validate_imports(sync_job_path, [
        'from google.cloud import bigquery',
        'from datetime import datetime',
        'amazon_client',
        'settings'
    ])
    print()
    
    # 3. Validate main.py routing
    print("3️⃣  Validating main.py routing...")
    main_path = base_path / "backend/main.py"
    
    all_valid &= validate_python_syntax(main_path)
    
    with open(main_path, 'r') as f:
        main_content = f.read()
    
    if "job_type == 'data_sync'" in main_content:
        print("✅ main.py: data_sync routing found")
    else:
        print("❌ main.py: data_sync routing not found")
        all_valid = False
    
    if "from jobs.data_sync.amazon_ads_sync import run_data_sync" in main_content:
        print("✅ main.py: data_sync import found")
    else:
        print("❌ main.py: data_sync import not found")
        all_valid = False
    print()
    
    # 4. Validate table creation scripts
    print("4️⃣  Validating table creation scripts...")
    
    create_tables_py = base_path / "scripts/create_sync_tables.py"
    all_valid &= validate_python_syntax(create_tables_py)
    
    create_tables_sql = base_path / "scripts/create_sync_tables.sql"
    if create_tables_sql.exists():
        print(f"✅ {create_tables_sql.name}: File exists")
        with open(create_tables_sql, 'r') as f:
            sql_content = f.read()
        
        required_tables = [
            'sp_campaigns',
            'sp_keywords', 
            'sp_campaign_performance',
            'keyword_performance',
            'sp_advertised_product_metrics'
        ]
        
        missing_tables = [t for t in required_tables if t not in sql_content]
        if missing_tables:
            print(f"❌ {create_tables_sql.name}: Missing tables: {missing_tables}")
            all_valid = False
        else:
            print(f"✅ {create_tables_sql.name}: All required tables defined")
    else:
        print(f"❌ {create_tables_sql.name}: File not found")
        all_valid = False
    print()
    
    # 5. Check directory structure
    print("5️⃣  Validating directory structure...")
    data_sync_dir = base_path / "backend/jobs/data_sync"
    
    if data_sync_dir.exists() and data_sync_dir.is_dir():
        print(f"✅ Directory exists: {data_sync_dir}")
    else:
        print(f"❌ Directory not found: {data_sync_dir}")
        all_valid = False
    
    init_file = data_sync_dir / "__init__.py"
    if init_file.exists():
        print(f"✅ __init__.py exists")
    else:
        print(f"❌ __init__.py not found")
        all_valid = False
    print()
    
    # Summary
    print("=" * 60)
    if all_valid:
        print("✅ All validations passed!")
        print("=" * 60)
        return 0
    else:
        print("❌ Some validations failed")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
