# Documentation-Writer Skill

Produce accurate, complete, and well-styled documentation by reading source truth first. Never document from memory.

---

## Steps

1. **Understand scope**
   - Identify every document to create or update
   - Identify the target audience (internal developers, end users, API consumers)
   - List each scope item explicitly before starting

2. **Read existing documentation**
   - Glob for existing docs in the same area
   - Read 2–3 existing docs to capture style, tone, heading structure, and terminology
   - Note any formatting conventions (code block style, admonition types, link format)

3. **Read the source**
   - Glob for the source files, interfaces, or modules being documented
   - Read only the public API surface and exported symbols
   - Note function signatures, parameter types, return values, and raised exceptions

4. **Draft**
   - Write documentation following existing conventions
   - Use concrete examples — at least one example per function or concept
   - For README files: include Quick Start, Installation, and Usage sections

5. **Cross-reference**
   - Check every function name, parameter, type, and example against the source
   - Fix any inaccuracies before proceeding

6. **Verify links**
   - Grep for all Markdown links `[text](url)` in modified files
   - Check that internal links point to files that actually exist

7. **Polish**
   - Read each section as a first-time reader would
   - Remove jargon, passive voice, and ambiguous pronouns
   - Ensure consistent terminology (choose one term per concept and stick to it)

8. **Final review**
   - Confirm every scope item from step 1 has been addressed
   - Report items completed, items updated, and any items deferred with reason
