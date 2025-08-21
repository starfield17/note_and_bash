# Guide to Configuring ROS2 Environment in Fish Shell

## Problem Description

ROS2's environment setup scripts (such as `setup.bash`) are written for the Bash shell, and the Fish shell cannot directly execute these Bash scripts. This results in the inability to use the `ros2` command in the Fish shell.

## Solution: Using the bass Plugin

[bass](https://github.com/edc/bass) is a Fish plugin that allows you to execute Bash commands and scripts within Fish. Below are the complete configuration steps:

### Step 1: Install the Fisher Plugin Manager

Fisher is a popular Fish plugin manager used for installing and managing Fish plugins.

1.  Install Fisher using the following command:

    ```bash
    curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source && fisher install jorgebucaran/fisher
    ```

2.  Verify that Fisher is installed successfully:

    ```bash
    fisher --version
    ```

### Step 2: Install the bass Plugin Using Fisher

```bash
fisher install edc/bass
```

### Step 3: Configure the ROS2 Environment

1.  Edit the Fish configuration file:

    ```bash
    vim ~/.config/fish/config.fish
    ```

2.  Find the ROS-related configuration section, which might look something like this:

    ```fish
    source /opt/ros/jazzy/setup.bash
    ```

3.  Modify it to use bass:

    ```fish
    bass source /opt/ros/jazzy/setup.bash
    ```

4.  Save and close the file (:wq)

### Step 4: Apply the Changes

There are two ways to apply the changes:

1.  Reload the configuration for the current shell:

    ```bash
    source ~/.config/fish/config.fish
    ```

2.  Or, close and reopen the terminal.

### Step 5: Verify the Configuration

Run the following command to verify that the ROS2 environment is configured correctly:

```bash
ros2 --help
```

If the ROS2 help information is output, the configuration is successful.

## Common Issues

### Issue: `fisher` command not found

Ensure your Fish shell version is 3.0.0 or newer:

```bash
fish --version
```

If the Fish version is too old, please update the Fish shell first.

### Issue: ROS2 commands still unavailable after bass installation

Check if the bass command is used correctly in your Fish configuration file:

```bash
cat ~/.config/fish/config.fish | grep bass
```

Ensure the syntax is `bass source /opt/ros/jazzy/setup.bash`, not `bass /opt/ros/jazzy/setup.bash` or any other form.

### Issue: Specific ROS2 package or functionality not found

You might need to install additional ROS2 packages. For example:

```bash
sudo apt install ros-jazzy-<package-name>
```

## Further Notes

-   After installing new ROS2 packages, you may need to re-source the environment or restart the terminal.
-   If you have multiple ROS2 distributions, ensure your `config.fish` file sources the correct version.
-   The bass plugin might slightly increase shell startup time. If this is a concern, consider manually sourcing the environment only when ROS2 is needed.

## Reference Links

-   [Fisher GitHub](https://github.com/jorgebucaran/fisher)
-   [bass GitHub](https://github.com/edc/bass)
-   [ROS2 Documentation](https://docs.ros.org/en/jazzy/)
