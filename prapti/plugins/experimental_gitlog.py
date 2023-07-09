""""
    Automatically log the conversation into git.
    Handle edits, backtrack and branch
"""
# ----------------------------------------------------------------------------
# /// DANGER -- UNDER CONSTRUCTION ///////////////////////////////////////////

import subprocess
import pathlib
import shlex
from datetime import datetime
from dataclasses import dataclass

from ..core.plugin import Plugin
from ..core.hooks import Hooks, HooksContext

# ----------------------------------------------------------------------------
# pathlib.Path.copy()
# https://stackoverflow.com/questions/33625931/copy-file-with-pathlib-in-python
# as to why pathlib.Path has a move method but not a copy method I do not know
def _Path_copy(self: pathlib.Path, target: pathlib.Path) -> None:
    import shutil
    assert self.is_file()
    shutil.copy(self, target)
    #shutil.copy(str(self), str(target))  # str() only there for Python < (3, 6)
pathlib.Path.copy = _Path_copy
# ----------------------------------------------------------------------------

def run_command(command: str, cwd: pathlib.Path, print_output=True) -> tuple[int, str]:
    command = shlex.split(command)
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8', cwd=cwd, check=False)
    print("command:", command, "cwd:", cwd)
    print("command output: --------------------------------")
    if print_output:
        print(process.stdout)
    return process.returncode, process.stdout # merged stdout and stderr

def get_git_revision_hashes(filename: str, cwd: pathlib.Path) -> list[str]:
    # return revision hashes ordered earliest to latest
    ret, output = run_command(f"git log --follow --oneline -- '{filename}'", cwd)
    if ret == 0: # success
        lines = output.splitlines()
        return [elems.split()[0] for elems in lines if elems.strip()]
    return []

@dataclass
class PrefixData:
    hash: str # hash of most recent commit that is a proper prefix of the current revision
    prefix: str # contents of "prefix" file at revision given by hash
    remainder: str # contents of the current revision following the prefix

def find_most_recent_proper_prefix(filename: str, hashes: list[str], cwd: pathlib.Path):
    """return the hash of the most recent revision that is a prefix of the file data
    this corresponds to a branch point. return None if no branch point was found or
    if the tip is a proper prefix"""
    if not hashes:
        return None
    current_file_data = (cwd / filename).read_text(encoding="utf-8")
    for hash_ in hashes: # searching from oldest to newest
        ret, earlier_file_data = run_command(f"git show '{hash_}:{filename}'", cwd, print_output=False) # read file data straight from git stdout
        assert ret == 0
        if current_file_data.startswith(earlier_file_data) or len(earlier_file_data) == 0:
            # we found a prefix
            print(f"found prefix at {hash_}")
            return PrefixData(hash=hash_, prefix=earlier_file_data, remainder=current_file_data[len(earlier_file_data):])
    return None

def should_backtrack(candidate_branch_point: PrefixData) -> bool:
    """given the candidate branch point, return True if it is appropriate to backtrack to that point and branch.
    (the alternative to backtracking is to commit the changes on the current branch as an "edit")
    This is currently a placehoder hack for a more elaborate text analysis.
    What we are trying to avoid is backtracking in cases where there is some small edit way up in the file
    but that the file should properly be considered an edit not a backtrack.
    Possible approaches are: ask an LLM, look at edit distances, parse as chat messages and look at what's changed
    (e.g. has the message structure changed? or just the contents?)
    Possibly, automatic backtracking may only occur in very limited scenarios, similar to what we have here.
    """
    if not candidate_branch_point.remainder.strip(): # at-most whitespace remainder
        # the change to the file is a trim
        return True
    if candidate_branch_point.remainder.count("### @") <= 1: # at most one message added beyond prefix
        return True
    return False

def make_branch_name(file_path: pathlib.Path) -> str:
    return datetime.now().strftime("%Y-%m-%d-%H%M%S")+f"-{file_path.name}"

class GitlogHooks(Hooks):
    def __init__(self):
        pass

    def on_plugin_loaded(self, context: HooksContext):
        """
        called when: the %plugins.load command loads the plugin.
        i.e. during command execution but before any response generation.
        """
        print("vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv")
        print("prapti.experimental.gitlog: on_plugin_loaded")
        print(f"{context.state.file_name = }")
        file_path = context.state.file_name.resolve()
        main_worktree_dir = file_path.parent
        shadow_worktree_dir = main_worktree_dir / ".prapti_shadow_worktree"
        gitignore_file = main_worktree_dir / ".gitignore"

        if not shadow_worktree_dir.exists():
            # FIXME: `git add worktree` will fail on an empty repo (until git 2.42) so do the following setup by hand
# """
# rm -rf .prapti_shadow_worktree
# git init

# # (+++ the following are only neede to put the repo into a sane state)
# git checkout --orphan noref
# touch .noref
# git add .noref
# git commit -m"repo setup"
# git rm .noref
# git commit -a -m 'repo setup'
# """
            # need git 2.42 https://stackoverflow.com/questions/53005845/checking-out-orphan-branch-in-new-work-tree/76552472#76552472
            # to use the --orphan flag, which will remove the need for +++ above
            run_command(f"git worktree add .prapti_shadow_worktree --detach", main_worktree_dir)

        if not gitignore_file.exists():
            gitignore_file.write_text(".prapti_shadow_worktree\n.prapticonfig\nprapti_reset\nprapti_reset.bat\n.gitignore", encoding="utf-8")

        print(f"{file_path.name = }, {main_worktree_dir = }")
        hashes = get_git_revision_hashes(file_path.name, main_worktree_dir)
        print(hashes)
        potential_branch_point = find_most_recent_proper_prefix(file_path.name, hashes, main_worktree_dir)
        commit_message = "user prompt"

        # three possibilities:
        # 1. the file is not added. add it on a new detached branch with the usual branch name
        # 2. the previous commit is a prefix of the current commit (i.e. it's a direct continuation) add and commit
        # 3. an earlier commit is a prefix (all the way back to the original empty file). backtrack and branch

        if not hashes:
            # the file has no hashes, it has never been comitted. add it
            branch_name = make_branch_name(file_path)
            print(f"gitlog: adding file {file_path.name} on new branch {branch_name}")
            if not context.root_config.dry_run:
                run_command(f"git checkout --orphan {branch_name}", shadow_worktree_dir)

                shadow_file_name = shadow_worktree_dir/file_path.name
                shadow_file_name.touch()
                run_command(f"git add {file_path.name}", shadow_worktree_dir)
                run_command(f"git commit -a -m 'empty file'", shadow_worktree_dir)

                file_path.copy(shadow_file_name) # copy our file into shadow worktree
                run_command(f"git commit -a -m '{commit_message}'", shadow_worktree_dir)
                run_command(f"git checkout --detach", shadow_worktree_dir) # to avoid error "fatal: ... is already checked out" below

                # put main worktree on new branch
                run_command(f"git switch --no-guess --force {branch_name}", main_worktree_dir)
            else:
                print("gitlog: dry run. no action taken")
        elif potential_branch_point is None or potential_branch_point.hash == hashes[0] or not should_backtrack(potential_branch_point):
            # the prefix is the current tip, the input is append-only, no need to branch
            print("gitlog: comitting modifications to current branch")

            if not context.root_config.dry_run:
                run_command(f"git commit -a -m '{commit_message}'", main_worktree_dir)
            else:
                print("gitlog: dry run. no action taken")
        else:
            # back-track and branch
            branch_name = make_branch_name(file_path)
            print(f"backtracking to {potential_branch_point.hash} and comitting modifications on new branch {branch_name}")
            if not context.root_config.dry_run:
                # create a branch at potential_branch_point.hash while leaving our input file unmodified
                # without geting errors about there being uncomitted changes

                # in shadow_worktree_dir:
                # create and check-out the branch in the shadow worktree
                # then copy and commit our work there
                run_command(f"git branch {branch_name} {potential_branch_point.hash}", shadow_worktree_dir)
                run_command(f"git checkout {branch_name}", shadow_worktree_dir)
                file_path.copy(shadow_worktree_dir/file_path.name) # copy our file into shadow worktree
                run_command(f"git commit -a -m '{commit_message}'", shadow_worktree_dir)
                run_command(f"git checkout --detach", shadow_worktree_dir) # to avoid error "fatal: ... is already checked out" below

                # in main_worktree_dir
                # checkout the branch in the main worktree (it already matches our working copy)
                # we can now continue work on the new branch

                # note that we need --merge to avoid an error about local changes
                # but there is no merge to perform because our local changes are already on the new branch
                run_command(f"git switch --no-guess --merge {branch_name}", main_worktree_dir)
            else:
                print("gitlog: dry run. no action taken")

        print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")

    def on_response_completed(self, context: HooksContext):
        """
        called after the file has been saved, flushed and closed, with the responses.
        """
        print("vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv")
        print("prapti.experimental.gitlog: on_response_completed")
        print(f"{context.state.file_name = }")

        main_worktree_dir = context.state.file_name.resolve().parent
        print(f"{context.state.file_name.name = }, {main_worktree_dir = }")

        if not context.root_config.dry_run:
            run_command(f"git commit -a -m 'assistant response'", main_worktree_dir)
        print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")

# ^^^ END UNDER CONSTRUCTION /////////////////////////////////////////////////
# ----------------------------------------------------------------------------

class GitlogPlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "0.1.0",
            name = "prapti.experimental.gitlog",
            version = "0.0.1",
            description = "Hooks for git conversation tracking"
        )

    def construct_hooks(self) -> Hooks|None:
        return GitlogHooks()

prapti_plugin = GitlogPlugin()
