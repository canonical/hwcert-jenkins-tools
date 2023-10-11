# Ubuntu Kernel Switcher

## Summary

Ubuntu Kernel Switcher is a utility that lets you switch to a specific
kernel. Notably, post-switch, that kernel becomes the default, ensuring
it remains after system updates introduce new kernels.

## Usage

To run the tool, use invoke `switch_kernel.py` with the desired kernel
as the argument. Examples:

- `switch_kernel.py 6.5`
- `switch_kernel.py generic`
- `switch_kernel.py 6.2.0-33-generic`
- `switch_kernel.py realtime`

Note how the argument is fuzzy matched. But beware, first match will be used
so for instance if `realtime` is used as the argument, first grub's menuentry
that matches `realtime` will be used.

## Testing

There `test_in_lxd_vm.py` is a script that tests the tool inside LXD's VMs.
(So it's somewhat safe to be used).
