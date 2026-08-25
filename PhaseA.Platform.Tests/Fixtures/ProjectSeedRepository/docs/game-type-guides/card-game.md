### Default Scenes
| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| class_selection | Class Selection | Choose class | Always | start | route_map | Choose a class. |
| route_map | Route Map | Choose route | Always | class_selection,reward_choice | card_battle | Choose a node. |
| card_battle | Card Battle | Fight | Always | route_map | reward_choice | Play cards. |
| reward_choice | Reward Choice | Choose reward | Always | card_battle | route_map | Choose a reward. |
### Required Modules
| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| route_map_path_selection | Route map path selection | Always | Routing | Choose reachable nodes. |
| hand_card_dragging | Hand cards | Always | Interaction | Drag cards. |
