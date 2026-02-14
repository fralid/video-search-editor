#!/usr/bin/env python3
"""
Skill Initializer - Creates a new skill from template

Usage:
    init_skill.py <skill-name> --path <path>

Examples:
    init_skill.py my-new-skill --path skills/public
    init_skill.py my-api-helper --path skills/private
    init_skill.py custom-skill --path /custom/location
"""

import sys
from pathlib import Path


SKILL_TEMPLATE = """---
name: {skill_name}
description: "[TODO: Полное и информативное объяснение того, что делает навык и когда его использовать. Включите КОГДА использовать этот навык - конкретные сценарии, типы файлов или задачи, которые его запускают.]"
---

# {skill_title}

## Обзор

[TODO: 1-2 предложения, объясняющие, что дает этот навык]

## Структурирование навыка

[TODO: Выберите структуру, которая лучше всего подходит для целей этого навыка. Распространенные паттерны:

**1. На основе рабочих процессов (Workflow-Based)** (лучше всего для последовательных процессов)
- Хорошо работает, когда есть четкие пошаговые процедуры
- Храните рабочие процессы в папке `workflows/`
- Структура: # Обзор -> # Список рабочих процессов -> # Детали

**2. На основе задач (Task-Based)** (лучше всего для наборов инструментов)
- Хорошо работает, когда навык предлагает разные операции/возможности
- Пример: Навык PDF с "Быстрый старт" -> "Объединить PDF" -> "Разделить PDF" -> "Извлечь текст"
- Структура: # Обзор -> # Быстрый старт -> # Категория задач 1 -> # Категория задач 2...

Удалите этот раздел "Структурирование навыка", когда закончите - это просто руководство.]

## [TODO: Замените на первый основной раздел на основе выбранной структуры]

[TODO: Добавьте контент сюда. См. примеры в существующих навыках:
- Примеры кода для технических навыков
- Деревья решений для сложных рабочих процессов
- Конкретные примеры с реалистичными запросами пользователей
- Ссылки на скрипты/шаблоны/справочники по мере необходимости]

## Ресурсы

Этот навык включает примеры каталогов ресурсов, демонстрирующие организацию различных типов пакетных ресурсов:

### workflows/
Агентные рабочие процессы (.md файлы), описывающие пошаговые процедуры.

### scripts/
Исполняемый код (Python/Bash/и т.д.), который можно запустить напрямую для выполнения конкретных операций.

### references/
Документация и справочные материалы, предназначенные для загрузки в контекст, чтобы информировать процесс мышления Агента.

### assets/
Файлы, не предназначенные для загрузки в контекст, а используемые в выводе, который создает Агент.

---

**Любые ненужные каталоги можно удалить.** Не каждому навыку требуются все типы ресурсов.
"""

EXAMPLE_SCRIPT = '''#!/usr/bin/env python3
"""
Example helper script for {skill_name}

This is a placeholder script that can be executed directly.
Replace with actual implementation or delete if not needed.
"""

def main():
    print("This is an example script for {skill_name}")
    # TODO: Add actual script logic here

if __name__ == "__main__":
    main()
'''

EXAMPLE_REFERENCE = """# Справочная документация для {skill_title}

Это заполнитель для подробной справочной документации (на русском языке).
Замените на актуальный справочный контент или удалите, если не требуется.

## Когда полезны справочные документы

Справочные документы идеальны для:
- Подробной документации API
- Детальных руководств по рабочим процессам
- Информации, слишком объемной для основного SKILL.md
"""

EXAMPLE_ASSET = """# Пример файла актива

Этот заполнитель представляет место, где будут храниться файлы активов.
Замените на актуальные файлы активов (шаблоны, изображения, шрифты и т.д.) или удалите, если не требуется.
"""

EXAMPLE_WORKFLOW = """---
description: Пример рабочего процесса для {skill_name}
---
# Пример Рабочего Процесса

Этот рабочий процесс демонстрирует возможности навыка {skill_title}.

1.  Шаг первый: Подготовка данных
2.  Шаг второй: Выполнение действия
    // turbo
3.  Шаг третий: Завершение
"""


def title_case_skill_name(skill_name):
    """Convert hyphenated skill name to Title Case for display."""
    return ' '.join(word.capitalize() for word in skill_name.split('-'))


def init_skill(skill_name, path):
    """
    Initialize a new skill directory with template SKILL.md.

    Args:
        skill_name: Name of the skill
        path: Path where the skill directory should be created

    Returns:
        Path to created skill directory, or None if error
    """
    # Determine skill directory path
    skill_dir = Path(path).resolve() / skill_name

    # Check if directory already exists
    if skill_dir.exists():
        print(f"❌ Error: Skill directory already exists: {skill_dir}")
        return None

    # Create skill directory
    try:
        skill_dir.mkdir(parents=True, exist_ok=False)
        print(f"✅ Created skill directory: {skill_dir}")
    except Exception as e:
        print(f"❌ Error creating directory: {e}")
        return None

    # Create SKILL.md from template
    skill_title = title_case_skill_name(skill_name)
    skill_content = SKILL_TEMPLATE.format(
        skill_name=skill_name,
        skill_title=skill_title
    )

    skill_md_path = skill_dir / 'SKILL.md'
    try:
        skill_md_path.write_text(skill_content, encoding='utf-8')
        print("✅ Created SKILL.md")
    except Exception as e:
        print(f"❌ Error creating SKILL.md: {e}")
        return None

    # Create resource directories with example files
    try:
        # Create workflows/ directory
        workflows_dir = skill_dir / 'workflows'
        workflows_dir.mkdir(exist_ok=True)
        example_workflow = workflows_dir / 'example_workflow.md'
        example_workflow.write_text(EXAMPLE_WORKFLOW.format(skill_name=skill_name, skill_title=skill_title), encoding='utf-8')
        print("✅ Created workflows/example_workflow.md")

        # Create scripts/ directory with example script
        scripts_dir = skill_dir / 'scripts'
        scripts_dir.mkdir(exist_ok=True)
        example_script = scripts_dir / 'example.py'
        example_script.write_text(EXAMPLE_SCRIPT.format(skill_name=skill_name), encoding='utf-8')
        example_script.chmod(0o755)
        print("✅ Created scripts/example.py")

        # Create references/ directory with example reference doc
        references_dir = skill_dir / 'references'
        references_dir.mkdir(exist_ok=True)
        example_reference = references_dir / 'api_reference.md'
        example_reference.write_text(EXAMPLE_REFERENCE.format(skill_title=skill_title), encoding='utf-8')
        print("✅ Created references/api_reference.md")

        # Create assets/ directory with example asset placeholder
        assets_dir = skill_dir / 'assets'
        assets_dir.mkdir(exist_ok=True)
        example_asset = assets_dir / 'example_asset.txt'
        example_asset.write_text(EXAMPLE_ASSET, encoding='utf-8')
        print("✅ Created assets/example_asset.txt")
    except Exception as e:
        print(f"❌ Error creating resource directories: {e}")
        return None

    # Print next steps
    print(f"\n✅ Skill '{skill_name}' initialized successfully at {skill_dir}")
    print("\nNext steps:")
    print("1. Edit SKILL.md to complete the TODO items and update the description (in Russian)")
    print("2. Customize or delete the example files in scripts/, references/, assets/, and workflows/")
    print("3. Run the validator when ready to check the skill structure")

    return skill_dir


def main():
    if len(sys.argv) < 4 or sys.argv[2] != '--path':
        print("Usage: init_skill.py <skill-name> --path <path>")
        print("\nSkill name requirements:")
        print("  - Hyphen-case identifier (e.g., 'data-analyzer')")
        print("  - Lowercase letters, digits, and hyphens only")
        print("  - Max 40 characters")
        print("  - Must match directory name exactly")
        print("\nExamples:")
        print("  init_skill.py my-new-skill --path skills/public")
        print("  init_skill.py my-api-helper --path skills/private")
        print("  init_skill.py custom-skill --path /custom/location")
        sys.exit(1)

    skill_name = sys.argv[1]
    path = sys.argv[3]

    print(f"🚀 Initializing skill: {skill_name}")
    print(f"   Location: {path}")
    print()

    result = init_skill(skill_name, path)

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
