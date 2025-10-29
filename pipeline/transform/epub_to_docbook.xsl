<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:h="http://www.w3.org/1999/xhtml">
  <xsl:param name="root-element" select="'book'"/>
  <xsl:output method="xml" indent="yes" encoding="UTF-8"/>

  <xsl:template match="/h:html">
    <xsl:element name="{$root-element}">
      <xsl:apply-templates select="h:body/*"/>
    </xsl:element>
  </xsl:template>

  <xsl:template match="h:h1">
    <title><xsl:value-of select="normalize-space(.)"/></title>
  </xsl:template>

  <xsl:template match="h:h2">
    <para role="section"><xsl:value-of select="normalize-space(.)"/></para>
  </xsl:template>

  <xsl:template match="h:p">
    <para><xsl:value-of select="normalize-space(.)"/></para>
  </xsl:template>

  <xsl:template match="h:ul">
    <itemizedlist>
      <xsl:apply-templates/>
    </itemizedlist>
  </xsl:template>

  <xsl:template match="h:ol">
    <orderedlist>
      <xsl:apply-templates/>
    </orderedlist>
  </xsl:template>

  <xsl:template match="h:li">
    <listitem><para><xsl:value-of select="normalize-space(.)"/></para></listitem>
  </xsl:template>

  <xsl:template match="h:img">
    <mediaobject>
      <imageobject>
        <imagedata fileref="{./@src}"/>
      </imageobject>
    </mediaobject>
  </xsl:template>

  <xsl:template match="h:figcaption">
    <caption><xsl:value-of select="normalize-space(.)"/></caption>
  </xsl:template>

  <xsl:template match="text()"/>
</xsl:stylesheet>
