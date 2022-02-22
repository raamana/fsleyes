/*
 * Fragment shader for colouring GLTractogram instances,
 * where streamlines are coloured according to their
 * orientation.
 */
#version 120

#pragma include phong_lighting.glsl

/*
 * Colours used for X/Y/Z orientation, and
 * scale/offset for applying global
 * brightness/contrast
 */
uniform vec4  xColour;
uniform vec4  yColour;
uniform vec4  zColour;
uniform float colourScale;
uniform float colourOffset;

/* Light position, and whether lighting affect should be applied. */
uniform vec3 lightPos;
uniform bool lighting;

/* Streamline orientation corresponding to this fragment. */
varying vec3 fragData0;

/*Vertex position and vertex normal, used for lighting. */
varying vec3 fragNormal;
varying vec3 fragVertex;

void main(void) {

  vec4 colour = fragData0.x * xColour +
                fragData0.y * yColour +
                fragData0.z * zColour;
  colour.xyz  = colour.xyz * colourScale + colourOffset;
  colour.a    = (xColour.a +
                 yColour.a +
                 zColour.a) / 3;

  if (lighting) {
    colour.xyz = phong_lighting(fragVertex, fragNormal, lightPos, colour.xyz);
  }

  gl_FragColor = colour;
}
