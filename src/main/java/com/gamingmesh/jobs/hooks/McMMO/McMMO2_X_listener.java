package com.gamingmesh.jobs.hooks.McMMO;

import java.lang.reflect.Method;
import java.util.HashMap;

import com.gamingmesh.jobs.listeners.JobsPaymentListener;
import org.bukkit.block.Block;
import org.bukkit.event.Cancellable;
import org.bukkit.event.Event;
import org.bukkit.plugin.Plugin;

import org.bukkit.GameMode;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.inventory.ItemStack;

import com.gamingmesh.jobs.Jobs;
import com.gamingmesh.jobs.actions.ItemActionInfo;
import com.gamingmesh.jobs.container.ActionType;
import com.gamingmesh.jobs.container.JobsPlayer;
import com.gamingmesh.jobs.hooks.JobsHook;
import com.gmail.nossr50.events.skills.abilities.McMMOPlayerAbilityActivateEvent;
import com.gmail.nossr50.events.skills.abilities.McMMOPlayerAbilityDeactivateEvent;
import com.gmail.nossr50.events.skills.repair.McMMOPlayerRepairCheckEvent;

public class McMMO2_X_listener implements Listener {

    @EventHandler
    public void OnItemrepair(McMMOPlayerRepairCheckEvent event) {
        Player player = event.getPlayer();
        // disabling plugin in world
        if (player == null || !Jobs.getGCManager().canPerformActionInWorld(player.getWorld()))
            return;

        ItemStack resultStack = event.getRepairedObject();
        if (resultStack == null)
            return;

        if (!Jobs.getPermissionHandler().hasWorldPermission(player, player.getLocation().getWorld().getName()))
            return;

        // check if in creative
        if (player.getGameMode().equals(GameMode.CREATIVE) && !player.hasPermission("jobs.paycreative") && !Jobs.getGCManager().payInCreative())
            return;

        JobsPlayer jPlayer = Jobs.getPlayerManager().getJobsPlayer(player);
        if (jPlayer == null)
            return;

        Jobs.action(jPlayer, new ItemActionInfo(resultStack, ActionType.REPAIR));
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void OnAbilityOn(McMMOPlayerAbilityActivateEvent event) {
        HashMap<String, Long> InfoMap = JobsHook.getMcMMOManager().getMap().computeIfAbsent(event.getPlayer().getUniqueId(), k -> new HashMap<>());
        InfoMap.put(event.getAbility().toString().toLowerCase(), System.currentTimeMillis() + (60 * 1000));
    }

    /**
     * Some mcMMO builds publish all affected logs in one custom event instead of
     * emitting separate block-break events. Register that optional event only if
     * it exists, keeping the standard mcMMO dependency unchanged.
     */
    public void registerBulkTreeFellerSupport(Jobs plugin) {
        Plugin mcMMO = plugin.getServer().getPluginManager().getPlugin("mcMMO");
        if (mcMMO == null)
            return;

        try {
            Class<?> rawEvent = Class.forName(
                    "com.gmail.nossr50.events.skills.woodcutting.TreeFellerDestroyTreeEvent",
                    false, mcMMO.getClass().getClassLoader());
            Class<? extends Event> eventType = rawEvent.asSubclass(Event.class);
            Method getPlayer = rawEvent.getMethod("getPlayer");
            Method getBlocks = rawEvent.getMethod("getBlocks");

            plugin.getServer().getPluginManager().registerEvent(eventType, this, EventPriority.MONITOR,
                    (listener, event) -> {
                        if (event instanceof Cancellable && ((Cancellable) event).isCancelled())
                            return;
                        try {
                            Object playerValue = getPlayer.invoke(event);
                            Object blocksValue = getBlocks.invoke(event);
                            if (!(playerValue instanceof Player))
                                return;
                            Player player = (Player) playerValue;
                            if (blocksValue instanceof Iterable<?>) {
                                for (Object value : (Iterable<?>) blocksValue) {
                                    if (value instanceof Block)
                                        JobsPaymentListener.handleBulkTreeFellerBlock((Block) value, player, plugin);
                                }
                            } else if (blocksValue instanceof Block[]) {
                                for (Block block : (Block[]) blocksValue)
                                    JobsPaymentListener.handleBulkTreeFellerBlock(block, player, plugin);
                            }
                        } catch (ReflectiveOperationException ex) {
                            plugin.getLogger().warning("Could not read mcMMO Tree Feller blocks: " + ex.getMessage());
                        }
                    }, plugin, true);
            JobsPaymentListener.enableBulkTreeFellerSupport();
        } catch (ClassNotFoundException ignored) {
            // Standard mcMMO dispatches BlockBreakEvent subclasses per log instead.
        } catch (ReflectiveOperationException | LinkageError | ClassCastException ex) {
            plugin.getLogger().warning("Optional mcMMO Tree Feller integration unavailable: " + ex.getMessage());
        }
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void OnAbilityOff(McMMOPlayerAbilityDeactivateEvent event) {
        HashMap<String, Long> InfoMap = JobsHook.getMcMMOManager().getMap().get(event.getPlayer().getUniqueId());
        if (InfoMap == null)
            return;
        InfoMap.remove(event.getAbility().toString().toLowerCase());
        if (InfoMap.isEmpty())
            JobsHook.getMcMMOManager().getMap().remove(event.getPlayer().getUniqueId());
    }
}
