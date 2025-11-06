# region AccessibilityAudit Description
# INPUT: None (scans all HTML files in templates directory)
# OUTPUT: Writes accessibility_report.json and prints a human-readable summary.
import os
import json
from bs4 import BeautifulSoup

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
REPORT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../accessibility_report.json'))

# region check_accessibility Description
# INPUT: html_path (str): Path to HTML file.
# OUTPUT: List of issues found.
def check_accessibility(html_path):
    issues = []
    with open(html_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # Check for missing lang attribute
    if not soup.html or not soup.html.get("lang"):
        issues.append({"type": "lang-missing", "msg": "<html> tag missing 'lang' attribute."})

    # Check for missing or duplicate IDs
    ids = set()
    for tag in soup.find_all(True):
        if tag.has_attr("id"):
            if tag["id"] in ids:
                issues.append({"type": "duplicate-id", "msg": f"Duplicate id '{tag['id']}' found."})
            ids.add(tag["id"])

    # Check for form labels
    for input_tag in soup.find_all(["input", "select", "textarea"]):
        if input_tag.get("type") == "hidden":
            continue
        label = None
        if input_tag.has_attr("id"):
            label = soup.find("label", attrs={"for": input_tag["id"]})
        if not label:
            parent = input_tag.find_parent("label")
            if not parent:
                issues.append({"type": "label-missing", "msg": f"Input '{input_tag}' missing associated label."})

    # Check for ARIA attributes
    for tag in soup.find_all(True):
        if tag.name in ["button", "a", "input", "select", "textarea"]:
            if not (tag.has_attr("aria-label") or tag.has_attr("aria-labelledby") or tag.has_attr("aria-describedby") or tag.get("type") == "hidden"):
                if tag.name == "a" and tag.get("href") and tag.text.strip():
                    continue  # visible link text is sufficient
                if tag.name == "button" and tag.text.strip():
                    continue  # visible button text is sufficient
                issues.append({"type": "aria-missing", "msg": f"{tag.name.title()} missing ARIA label or visible text: {str(tag)[:80]}..."})

    # Check for tabindex
    for tag in soup.find_all(True):
        if tag.name in ["a", "button", "input", "select", "textarea"] and not tag.has_attr("tabindex"):
            issues.append({"type": "tabindex-missing", "msg": f"{tag.name.title()} missing tabindex attribute: {str(tag)[:80]}..."})

    return issues
# endregion check_accessibility Description

# region main Description
# INPUT: None
# OUTPUT: Writes accessibility_report.json and prints summary.
def main():
    report = {}
    for fname in os.listdir(TEMPLATE_DIR):
        if fname.endswith(".html"):
            path = os.path.join(TEMPLATE_DIR, fname)
            issues = check_accessibility(path)
            report[fname] = issues
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("Accessibility Audit Report:")
    for fname, issues in report.items():
        print(f"\nFile: {fname}")
        if not issues:
            print("  [OK] No issues found.")
        for i, issue in enumerate(issues, 1):
            print(f"  [{i}] {issue['type']}: {issue['msg']}")
# endregion main Description

if __name__ == "__main__":
    main()
# endregion AccessibilityAudit Description 