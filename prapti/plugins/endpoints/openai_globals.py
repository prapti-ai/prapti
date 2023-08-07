from dataclasses import dataclass
import openai

@dataclass
class OpenAIGlobals:
    api_key: str|None
    organization: str|None
    api_base: str
    api_type: str
    api_version: str|None

# save OpenAI global variables to avoid interference between modules that use them
# this relies on the openai_globals module being loaded before any changes are made
# to the globals. therefore we must load this module in every other module that imports openai
saved_openai_globals = OpenAIGlobals(
    api_key=openai.api_key,
    organization=openai.organization,
    api_base=openai.api_base,
    api_type=openai.api_type,
    api_version=openai.api_version)

def restore_openai_globals(openai_globals: OpenAIGlobals):
    openai.api_key = openai_globals.api_key
    openai.organization = openai_globals.organization
    openai.api_base = openai_globals.api_base
    openai.api_type = openai_globals.api_type
    openai.api_version = openai_globals.api_version
