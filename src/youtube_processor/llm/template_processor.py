"""Template loading and processing for knowledge extraction"""
from pathlib import Path
from typing import Optional


class TemplateError(Exception):
    """Template-related errors"""
    pass


class TemplateProcessor:
    """Loads and validates extraction templates"""

    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize template processor.

        Args:
            templates_dir: Path to templates directory.
                         Defaults to youtube_processor/resources/templates/
        """
        if templates_dir is None:
            # Default to package resources
            module_dir = Path(__file__).parent.parent
            templates_dir = module_dir / "resources" / "templates"

        self.templates_dir = Path(templates_dir)

        if not self.templates_dir.exists():
            raise TemplateError(
                f"Templates directory not found: {self.templates_dir}"
            )

    def load_template(self, version: str = "v2.1") -> str:
        """
        Load extraction template by version.

        Args:
            version: Template version (e.g., "v2.1")

        Returns:
            Template content as string

        Raises:
            TemplateError: If template file not found
        """
        template_file = self.templates_dir / f"extraction_template_{version}.md"

        if not template_file.exists():
            raise TemplateError(
                f"Template {version} not found at {template_file}"
            )

        return template_file.read_text(encoding="utf-8")

    def validate_template(self, template: str) -> bool:
        """
        Validate template has required sections.

        Args:
            template: Template content

        Returns:
            True if valid

        Raises:
            TemplateError: If template missing required sections
        """
        required_sections = [
            "KNOWLEDGE UNITS EXTRACTION",
            "1. Techniques Extracted",
            "2. Patterns Extracted",
            "3. Use Cases Extracted",
            "4. Capabilities Catalog",
            "5. Integration Methods",
            "6. Anti-Patterns Catalog",
            "7. Architecture Components",
            "8. Troubleshooting Knowledge",
            "9. Configuration Recipes",
            "10. Code Snippets Library"
        ]

        missing = []
        for section in required_sections:
            if section not in template:
                missing.append(section)

        if missing:
            raise TemplateError(
                f"Template missing required sections: {', '.join(missing)}"
            )

        return True

    def get_available_templates(self) -> list[str]:
        """List available template versions"""
        templates = []
        for file in self.templates_dir.glob("extraction_template_*.md"):
            # Extract version from filename: extraction_template_v2.1.md -> v2.1
            version = file.stem.replace("extraction_template_", "")
            templates.append(version)
        return sorted(templates)