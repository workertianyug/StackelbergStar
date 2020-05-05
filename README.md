To use this repository, first install the library https://github.com/BurnySc2/python-sc2

Then run python3.7 StackelbergBot.py

StackelbergStar would play against builtin AI

To play against StackelbergStar, change the main function to

```
def main():
    sc2.run_game(
        sc2.maps.get("(2)CatalystLE"),
        [Human(Race.Protoss),Bot(Race.Protoss, StackelbergBot(), name="StackelbergBot")],
        realtime=True,
    )
```