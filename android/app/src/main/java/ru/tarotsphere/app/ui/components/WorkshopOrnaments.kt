package ru.tarotsphere.app.ui.components

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.material3.HorizontalDivider
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.dp
import ru.tarotsphere.app.R
import ru.tarotsphere.app.ui.theme.FrameGold

@Composable
fun WorkshopBrand(modifier: Modifier = Modifier) {
    Image(painterResource(R.drawable.sphere_mark), contentDescription = null,
        modifier = modifier.clearAndSetSemantics {})
}

@Composable
fun WorkshopDivider(modifier: Modifier = Modifier) {
    val line = FrameGold.copy(alpha = .65f)
    Row(modifier.fillMaxWidth().clearAndSetSemantics {}, verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        HorizontalDivider(Modifier.weight(1f), thickness = .7.dp, color = line)
        SphereEmblem(Modifier.size(24.dp), FrameGold)
        HorizontalDivider(Modifier.weight(1f), thickness = .7.dp, color = line)
    }
}
