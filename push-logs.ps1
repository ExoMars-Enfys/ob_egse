# As of 2025-09-30, the OBSE logs/ directory is a git repository. This gives
# us a backup and makes it reasonably easy for us to get hold of the latest
# logs wherever we are. This script just does a simple add/commit/push of
# the logs directory.

git -C c:/wdir/ob_egse/logs add .
git -C c:/wdir/ob_egse/logs commit -a -m "Logs update"
git -C c:/wdir/ob_egse/logs push
