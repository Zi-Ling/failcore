# failcore/infra/rulesets/filesystem.py
"""
FileSystem RuleSet Loader

Loads rulesets from YAML files on disk
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from pathlib import Path
import yaml
import re

from failcore.core.rules.loader import RuleSetLoader
from failcore.core.rules.models import (
    RuleSet,
    Rule,
    RuleCategory,
    RuleSeverity,
    RuleAction,
    RuleMetadata,
    Pattern,
    PolicyMatrix,
    ThresholdConfig,
    ToolMapping,
)


class FileSystemLoader(RuleSetLoader):
    """
    Load rulesets from YAML files
    
    Directory structure:
        {base_path}/
            dlp.yml
            semantic.yml
            effects.yml
            taint.yml
            drift.yml
    
    File format:
        name: dlp
        version: "1.0.0"
        description: "DLP patterns"
        rules:
          - rule_id: "DLP-001"
            name: "OpenAI API Key"
            category: "dlp.api_key"
            severity: "high"
            patterns:
              - pattern_type: "regex"
                value: "sk-[A-Za-z0-9]{32,}"
    """
    
    def __init__(self, base_path: str | Path):
        """
        Initialize filesystem loader
        
        Args:
            base_path: Base directory containing ruleset YAML files
        """
        self.base_path = Path(base_path).expanduser().resolve()
        self._cache: Dict[str, RuleSet] = {}
    
    def load_ruleset(self, name: str) -> Optional[RuleSet]:
        """
        Load a ruleset by name
        
        Args:
            name: Ruleset name (e.g., "dlp", "semantic")
        
        Returns:
            RuleSet if found, None otherwise
        """
        # Check cache first
        if name in self._cache:
            return self._cache[name]
        
        # Try to load from file
        yml_path = self.base_path / f"{name}.yml"
        yaml_path = self.base_path / f"{name}.yaml"
        
        file_path = None
        if yml_path.exists():
            file_path = yml_path
        elif yaml_path.exists():
            file_path = yaml_path
        
        if not file_path:
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            ruleset = self._parse_ruleset(data)
            self._cache[name] = ruleset
            return ruleset
        
        except Exception as e:
            print(f"Error loading ruleset {name}: {e}")
            return None
    
    def list_available_rulesets(self) -> List[str]:
        """List all available ruleset names"""
        if not self.base_path.exists():
            return []
        
        names = []
        for file_path in self.base_path.glob("*.yml"):
            names.append(file_path.stem)
        for file_path in self.base_path.glob("*.yaml"):
            if file_path.stem not in names:
                names.append(file_path.stem)
        
        return sorted(names)
    
    def reload(self) -> None:
        """Reload all rulesets from disk"""
        self._cache.clear()
    
    def _parse_ruleset(self, data: Dict[str, Any]) -> RuleSet:
        """Parse ruleset from YAML data"""
        rules = []
        for rule_data in data.get("rules", []):
            rule = self._parse_rule(rule_data)
            if rule:
                rules.append(rule)
        
        return RuleSet(
            name=data.get("name", "unknown"),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            rules=rules,
            metadata=data.get("metadata", {}),
        )
    
    def _parse_rule(self, data: Dict[str, Any]) -> Optional[Rule]:
        """Parse rule from YAML data"""
        try:
            # Parse category
            category_str = data.get("category", "")
            try:
                category = RuleCategory(category_str)
            except ValueError:
                print(f"Invalid category: {category_str}")
                return None
            
            # Parse severity
            severity_str = data.get("severity", "medium")
            try:
                severity = RuleSeverity(severity_str)
            except ValueError:
                severity = RuleSeverity.MEDIUM
            
            # Parse action
            action_str = data.get("action", "warn")
            try:
                action = RuleAction(action_str)
            except ValueError:
                action = RuleAction.WARN
            
            # Parse patterns
            patterns = []
            for pattern_data in data.get("patterns", []):
                pattern = self._parse_pattern(pattern_data)
                if pattern:
                    patterns.append(pattern)
            
            # Parse metadata
            metadata = RuleMetadata(
                source=data.get("source", "builtin"),
                version=data.get("version", "1.0.0"),
                author=data.get("author"),
                trust_level=data.get("trust_level", "trusted"),
                tags=data.get("tags", []),
                references=data.get("references", []),
            )
            
            return Rule(
                rule_id=data.get("rule_id", ""),
                name=data.get("name", ""),
                category=category,
                severity=severity,
                description=data.get("description", ""),
                patterns=patterns,
                action=action,
                metadata=metadata,
                enabled=data.get("enabled", True),
                config=data.get("config", {}),
                examples=data.get("examples", []),
                false_positive_rate=data.get("false_positive_rate", 0.0),
                performance_impact=data.get("performance_impact", "low"),
            )
        
        except Exception as e:
            print(f"Error parsing rule: {e}")
            return None
    
    def _parse_pattern(self, data: Dict[str, Any]) -> Optional[Pattern]:
        """Parse pattern from YAML data"""
        try:
            pattern_type = data.get("pattern_type", "regex")
            value = data.get("value", "")
            flags = data.get("flags", 0)
            
            # Parse regex flags
            if isinstance(flags, str):
                flag_value = 0
                if "i" in flags.lower():
                    flag_value |= re.IGNORECASE
                if "m" in flags.lower():
                    flag_value |= re.MULTILINE
                if "s" in flags.lower():
                    flag_value |= re.DOTALL
                flags = flag_value
            
            return Pattern(
                pattern_type=pattern_type,
                value=value,
                flags=flags,
            )
        
        except Exception as e:
            print(f"Error parsing pattern: {e}")
            return None


__all__ = ["FileSystemLoader"]
