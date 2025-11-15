.PHONY: demo demo-rviz views kill

demo:
	@WITH_RVIZ=0 tmuxp load -d ~/.config/tmuxp/gp2-demo.yaml
	@WITH_RVIZ=0 ~/gp2/tools/open_views.sh

demo-rviz:
	@WITH_RVIZ=1 tmuxp load -d ~/.config/tmuxp/gp2-demo.yaml
	@WITH_RVIZ=1 ~/gp2/tools/open_views.sh

views:
	@~/gp2/tools/open_views.sh

kill:
	-@tmux kill-session -t gp2-demo 2>/dev/null || true
