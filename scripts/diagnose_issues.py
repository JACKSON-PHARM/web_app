#!/usr/bin/env python3
"""
Diagnostic script to check for common issues in the PharmaStock web app
"""
import os
import sys
import re
from pathlib import Path

def check_file_syntax(file_path):
    """Check for common syntax errors in HTML/JS files"""
    issues = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            
        # Check for unclosed script tags
        script_open = content.count('<script>') + content.count('<script ')
        script_close = content.count('</script>')
        if script_open != script_close:
            issues.append(f"⚠️ Mismatched script tags: {script_open} open, {script_close} close")
        
        # Check for common JavaScript syntax issues
        # Check for unclosed brackets in JavaScript sections
        in_script = False
        bracket_count = 0
        paren_count = 0
        brace_count = 0
        
        for i, line in enumerate(lines, 1):
            if '<script' in line and '</script>' not in line:
                in_script = True
            if '</script>' in line:
                in_script = False
                if bracket_count != 0 or paren_count != 0 or brace_count != 0:
                    issues.append(f"⚠️ Line {i}: Unclosed brackets/parens/braces in script section")
                bracket_count = paren_count = brace_count = 0
            
            if in_script:
                bracket_count += line.count('[') - line.count(']')
                paren_count += line.count('(') - line.count(')')
                brace_count += line.count('{') - line.count('}')
        
        # Check for apiRequest function calls
        if 'apiRequest' in content and 'function apiRequest' not in content and 'async function apiRequest' not in content:
            # Check if it's in base.html (which should have it)
            if 'dashboard.html' in str(file_path):
                issues.append("⚠️ apiRequest function called but may not be defined (should be in base.html)")
        
        # Check for common null reference patterns
        null_ref_patterns = [
            r'\.style\.display\s*=',
            r'\.style\.\w+\s*=',
        ]
        for pattern in null_ref_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                # Check if there's a null check before this
                context = content[max(0, match.start()-100):match.start()]
                if 'if (' not in context and '&&' not in context:
                    issues.append(f"⚠️ Line {line_num}: Potential null reference - {match.group()}")
        
    except Exception as e:
        issues.append(f"❌ Error reading file: {e}")
    
    return issues

def check_api_endpoints():
    """Check if API endpoints exist"""
    issues = []
    api_files = [
        'web_app/app/api/dashboard.py',
        'web_app/app/api/stock_view.py',
    ]
    
    for api_file in api_files:
        if not os.path.exists(api_file):
            issues.append(f"❌ API file missing: {api_file}")
        else:
            with open(api_file, 'r') as f:
                content = f.read()
                if '/api/dashboard/branches' in content or 'branches' in content:
                    if '@router.get' not in content and 'def get' not in content:
                        issues.append(f"⚠️ {api_file}: May be missing branches endpoint")
    
    return issues

def main():
    print("Running PharmaStock Web App Diagnostics...\n")
    
    all_issues = []
    
    # Check dashboard.html
    dashboard_file = Path('web_app/templates/dashboard.html')
    if dashboard_file.exists():
        print(f"📄 Checking {dashboard_file}...")
        issues = check_file_syntax(dashboard_file)
        if issues:
            all_issues.extend(issues)
            for issue in issues:
                print(f"  {issue}")
        else:
            print("  ✅ No syntax issues found")
    else:
        print(f"  ❌ File not found: {dashboard_file}")
    
    # Check base.html
    base_file = Path('web_app/templates/base.html')
    if base_file.exists():
        print(f"\n📄 Checking {base_file}...")
        issues = check_file_syntax(base_file)
        if issues:
            all_issues.extend(issues)
            for issue in issues:
                print(f"  {issue}")
        else:
            print("  ✅ No syntax issues found")
    
    # Check stock_view.html
    stock_view_file = Path('web_app/templates/stock_view.html')
    if stock_view_file.exists():
        print(f"\n📄 Checking {stock_view_file}...")
        issues = check_file_syntax(stock_view_file)
        if issues:
            all_issues.extend(issues)
            for issue in issues:
                print(f"  {issue}")
        else:
            print("  ✅ No syntax issues found")
    
    # Check API endpoints
    print(f"\n📡 Checking API endpoints...")
    issues = check_api_endpoints()
    if issues:
        all_issues.extend(issues)
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  ✅ API endpoints look good")
    
    # Summary
    print(f"\n{'='*60}")
    if all_issues:
        print(f"[ERROR] Found {len(all_issues)} issue(s) that need attention")
        print("\nRecommendations:")
        print("1. Fix null reference errors by adding null checks")
        print("2. Ensure all script tags are properly closed")
        print("3. Check browser console for runtime errors")
        print("4. Verify API endpoints are accessible")
    else:
        print("[OK] No obvious syntax issues found!")
        print("\nIf issues persist:")
        print("1. Clear browser cache and hard refresh (Ctrl+Shift+R)")
        print("2. Check browser console for runtime errors")
        print("3. Verify API endpoints are responding")
        print("4. Check server logs for errors")

if __name__ == '__main__':
    main()

