# AGENTS.md

## Purpose

This repo contains `erza`, a language project aimed at terminal user interface
creation.

## Scope

- Keep the repo focused on the language, compiler/runtime, tooling, and examples
  for TUI apps only.
- Treat `.erza` component files as the primary authoring surface.
- Use an HTML-like component structure with PHP-style template delimiters as an
  intentional authoring model, while keeping the rendered output terminal-native.
- Keep `.erza` syntax language-neutral even when a prototype backend is written
  in Python.
- Keep backend integration language-agnostic at the product level.
- Make `hjkl` the default navigation model for focus movement and component
  traversal.
- Treat transparent or no-color backgrounds as the visual default.
- Inherit the user's terminal font instead of specifying or shipping one.
- Use Python as the default prototype backend in docs and early implementations.
- Keep early commits small and easy to revise while the language shape is fluid.

## Guardrails

- Do not add a web UI or unrelated service code unless explicitly requested.
- Do not expand the scope back to generic CLI tooling unless explicitly
  requested.
- Do not make mouse-first, arrow-only, or high-chrome navigation the default.
- Do not introduce a forced background color unless the user explicitly asks for
  it.
- Do not attempt to control terminal font choice from `erza`.
- Prefer clear design docs and small prototypes over speculative large frameworks.
- Preserve the spelling `erza` unless the user explicitly renames the project.
