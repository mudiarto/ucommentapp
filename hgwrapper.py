"""
Wraps the standard DVCS commands: for mercurial.
"""
from mercurial import ui, hg, commands, cmdutil, util, url, error
from mercurial.node import nullid, short
from mercurial.i18n import _
from mercurial.lock import release

ui_obj = ui.ui()
ui_obj.quiet = True
ui_obj.verbose = False

class DVCSError(Exception):
    pass

def get_hg_repo(repo):
    """
    Returns a Mercurial repository object, even if ``repo`` is specified as the
    (string) location of the repository.
    """
    if isinstance(repo, basestring):
        try:
            repo = hg.repository(ui_obj, repo, create=False)
        except error.RepoError as err:
            raise DVCSError(err)
        repo.ui.quiet = ui_obj.quiet
        repo.ui.verbose = ui_obj.verbose
    return repo

def get_revision_info(repo=None):
    """
    Returns the changeset information for a repository, as a tuple:
    (integer revision number, unique hexadecimal string)
    """
    repo = get_hg_repo(repo)
    try:
        parent, dummy = repo.dirstate.parents()
        return repo.changelog.rev(parent), short(parent)
    except AttributeError:
        parent = repo.lookup('tip')
        return -1, short(parent) # we never use the remote repo's revision num

def init(dest):
    """
    Creates a repository in the destination directory.

    This function is not required in ucomment; it is only used for unit-testing.
    """
    out = commands.init(ui_obj, dest)
    if out != None and out != 0:
        raise DVCSError('Could not initialize the repository at %s' % dest)


def add(repo, *pats):
    """
    Adds one or more files to the repository, using Mercurial's syntax for
    ``hg add``.  See ``hg help patterns`` for the syntax.

    This function is not required in ucomment; it is only used for unit-testing.
    """
    repo = get_hg_repo(repo)
    out = commands.add(ui_obj, repo, *pats)
    if out != None and out != 0:
        raise DVCSError('Could not correctly add all files')

def check_out(repo=None, rev='tip'):
    """
    Operates on the given repository, ``repo``, and checks out the revision
    to the given revision number.  The default revision is the `tip`.

    Returns the revision info after update, so that one can verify the update
    succeeded.
    """
    repo = get_hg_repo(repo)
    # Use str(0), because 0 by itself evaluates to None in Python logical checks
    commands.update(ui_obj, repo, rev=str(rev))
    return get_revision_info(repo)

def clone_repo(source, dest):
    """ Creates a clone of the remote repository given by the ``source`` URL,
    and places it at the destination URL given by ``dest``.

    Returns the changeset information for the local repository.
    """
    commands.clone(ui_obj, source, dest=dest)

def commit(repo, message):
    """
    Commit changes to the ``repo`` repository, with the given commit ``message``
    """
    # Username making commit: ui.config('ui', 'username')
    repo = get_hg_repo(repo)
    commands.commit(ui_obj, repo, message=message)

def commit_and_push_updates(message, local, remote, update_remote=False):
    """
    After making changes to file(s), programatically commit them to the
    ``local`` repository, with the given commit ``message``; then push changes
    back to the ``remote`` repository.

    You may optionally want to update the remote repositry also (default=False).
    """
    # Username making commit: ui.config('ui', 'username')
    local_repo = get_hg_repo(local)
    remote_repo = get_hg_repo(remote)
    # Merge in the local repo first
    update_requires_manual_merge = commands.update(ui_obj, local_repo)
    if update_requires_manual_merge:
        return False, False

    # Then commit the changes
    commands.commit(ui_obj, local_repo, message=message)

    # TODO(KGD): removed the prepush (not available in hg 1.6.2)
    #            replace it with something else? What was the need for it again?
    # Push that commit back to the remote repo.  Are we going to create a
    # remote head with this push?
    #check = local_repo.prepush(remote_repo, force=False, revs=None)
    #if check[0] is not None:
        # No: continue pushing the changes the remote repo
    local_repo.push(remote_repo)
    #else:
        ## Yes: pull in any changes first
        ##      then merge these changes
        ##      make the intended commit
        ##      finally, push back the new changes
        #local_repo.pull(remote_repo)

        ## The above check raises a false positive only if the repo
        ## being merged is the current repo.
        #try:
            #commands.merge(ui_obj, local_repo, node=None)
        #except error.Abort as err:
            #if str(err) == 'there is nothing to merge':
                #local_repo.push(remote_repo)
            #else:
                #raise DVCSError(err)
        ## TODO(KGD): how to get status messages out from merge: want to log them
        #message = 'First pulled and merged due to multiple heads. ' + message
        #commands.commit(ui_obj, local_repo, message=message)
        #local_repo.push(remote_repo)

    # Then update the remote repo (optional)
    if update_remote:
        commands.update(ui_obj, remote_repo)

    return get_revision_info(local_repo)

def pull_update_and_merge(local, remote):
    """
    Pulls, updates and merges changes from the other ``remote`` repository into
    the ``local`` repository.

    Does not handle the case when the changeset introduces a new head.

    Will always update to the tip revision.
    """
    # Wrap any errors into a single error type and return that back to Django.
    try:
        # hg pull -u, hg merge, hg commit
        local_repo = get_hg_repo(local)
        remote_repo = get_hg_repo(remote)

        # Pull in all changes from the remote repo
        result_pull = commands.pull(ui_obj, local_repo,
                                    source=remote,
                                    rev=['tip'])

        # Next, Update the local repo
        commands.update(ui_obj, local_repo)

        # Anything to merge?
        new_heads = local_repo.pull(remote_repo)

        # Merge any changes:
        if new_heads:
            merge_error = commands.merge(ui_obj, local_repo)

            # Commit any changes from the merge
            if not merge_error:
                commit(local_repo, message= ('Auto commit - ucomment hgwrapper:'
                                             ' updated and merged changes.'))

    except (error.Abort, error.RepoError) as err:
        raise DVCSError(err)
